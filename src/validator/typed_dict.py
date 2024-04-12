import inspect
import asyncio

from typing import Type, TypeVar, Generic, TypeAlias, Union, Optional, Callable, Awaitable, Any, Annotated
import typing
from dataclasses import dataclass
from typeguard import check_type

from .serializer import BaseSerializer, Serializable

T = TypeVar('T')
MaybeAwaitable: TypeAlias = Union[T, Awaitable[T]]

Without: TypeAlias = \
    Union[Callable[['TypedDict', Serializable], None],
          Callable[['TypedDict', Serializable], Awaitable[None]]]

Default: TypeAlias = \
    Union[Callable[['TypedDict'], Optional[T]],
          Callable[['TypedDict'], Awaitable[Optional[T]]]]

class MissingType:
    def __repr__(self):
        return "MISSING"

MISSING = MissingType()
Maybe: TypeAlias = Union[T, MissingType]

@dataclass
class TdField(Generic[T]):
    name: str
    type: Type[T]
    default: Maybe[T] = MISSING

def without(*names: str):
    def _inner(func: Without):
        setattr(func, "_td_without", names)
        return func
    return _inner

def default(*names: str):
    def _inner(func: Default):
        setattr(func, "_td_default", names)
        return func
    return _inner

@dataclass
class DefaultEntry:
    from_decorator: bool
    f: Default

class TypedDictMeta(type):
    def __new__(mcs, name, bases, attrs):
        cls = super().__new__(mcs, name, bases, attrs)
        cls._TD_FIELDS = {}
        cls._TD_WITHOUTS = {}
        cls._TD_DEFAULTS = {}

        # find any fields in base classes
        for base in cls.__mro__[-1:0:-1]:
            for field_name, field in getattr(base, "_TD_FIELDS", {}).items():
                cls._TD_FIELDS[field_name] = TdField(
                    name=field.name,
                    type=field.type,
                    default=field.default
                )
            cls._TD_WITHOUTS.update(getattr(base, "_TD_WITHOUTS", {}))
            cls._TD_DEFAULTS.update(getattr(base, "_TD_DEFAULTS", {}))

        annotateds = set()

        def add_default(name, **kwargs):
            if name in cls._TD_DEFAULTS:
                del cls._TD_DEFAULTS[name]
            cls._TD_DEFAULTS[name] = DefaultEntry(**kwargs)

        # find our own fields
        cls_annotations = inspect.get_annotations(cls)
        for name, type in cls_annotations.items():
            # skip special annotations
            if name in ["_TD_FIELDS", "_TD_WITHOUTS", "_TD_DEFAULTS"]:
                continue

            default = getattr(cls, name, MISSING)

            # handle default factories through Annotated:
            # Annotated[list, lambda: [4, 5]] should default to [4, 5]
            if typing.get_origin(type) is Annotated:
                if default is not MISSING:
                    raise ValueError(
                        f"in {name}: default supplied for annotated")
                type, default_factory = typing.get_args(type)
                annotateds.add(name)
                add_default(name, from_decorator=False, f=default_factory)

            elif default is not MISSING:
                # here, we don't provide a default OR a default factory.
                # normally, we just error, but there are a few common cases
                # that we should handle:

                # if we don't provide an Annotated and expect a required,
                # default-instantiable TypedDict, we just create the TypedDict
                # automatically
                if inspect.isclass(type) and \
                    issubclass(type, TypedDict) and \
                    type.default_instantiable():

                    if default is not MISSING:
                        continue

                    add_default(name, from_decorator=False, f=default_factory)

                elif (origin := typing.get_origin(type)) is not None and \
                        issubclass(origin, (dict, list)):
                    add_default(name, from_decorator=False, f=default_factory)

            cls._TD_FIELDS[name] = TdField(name, type, default)

        # find our withouts and defaults
        for attr in attrs.values():
            for field_name in getattr(attr, "_td_without", []):
                if field_name in cls._TD_WITHOUTS:
                    del cls._TD_WITHOUTS[field_name]
                cls._TD_WITHOUTS[field_name] = attr

            for field_name in getattr(attr, "_td_default", []):
                if cls._TD_FIELDS[field_name].default is not MISSING:
                    raise TypeError(
                        f"in {name}: "
                        f"{field_name} had both default and @default")
                if field_name in annotateds:
                    raise TypeError(
                        f"in {name}: "
                        f"{field_name} had both @default and annotated")
                add_default(name, from_decorator=True, f=attr)

        return cls

Coerce: TypeAlias = Union[
    Callable[[Any, Type[T]], Optional[T]],
    Callable[[Any, Type[T]], Awaitable[Optional[T]]]]

# TODO: __eq__, __hash__, __repr__
class TypedDict(metaclass=TypedDictMeta):

    _TD_FIELDS: dict[str, TdField] = {}
    _TD_WITHOUTS: dict[str, Without] = {}
    _TD_DEFAULTS: dict[str, DefaultEntry] = {}

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    # True if all fields have a default or default_factory
    @classmethod
    def default_instantiable(cls) -> bool:
        needs_factory = {
            f.name for f in cls._TD_FIELDS.values() if f.default is MISSING}
        factories = {*cls._TD_DEFAULTS.keys()}
        return len(needs_factory - factories) == 0

    @classmethod
    async def create(cls, **kwargs):
        return await cls._create(check_type, False, **kwargs)

    # a more general version of _create. allows an arbitrary
    # function to coerce input values into their required types.
    # substituting type_check for a data deserialization scheme, for instance,
    # allows us to deserialize kwargs with the same logic we use to instantiate
    @classmethod
    async def _create(cls, coerce: Coerce, run_withouts=False, /, **kwargs):

        # check for extra garbage keys
        extra_keys = set(kwargs.keys()) - set(cls._TD_FIELDS.keys())
        if extra_keys:
            raise TypeError(
                f"{cls.__qualname__} got some extraneous keys: "
                f"{extra_keys}")

        init_kwargs = {}
        init_kwarg_tasks = {}

        # first: find all existing keys and try to coerce them
        for name, field in cls._TD_FIELDS.items():
            if name in kwargs:
                coerced = coerce(kwargs[name], field.type)
                if asyncio.iscoroutine(coerced):
                    init_kwarg_tasks[name] = asyncio.create_task(coerced)
                else:
                    init_kwargs[name] = coerced
            # then: find all defaults and try to coerce them
            elif field.default is not MISSING:
                init_kwargs[name] = field.default

        # then: check for fields without defaults/withouts and crash if they
        # aren't filled in.

        # we do this here because we assume this is due to a larger protocol
        # error, rather than something getting deleted while the bot is down.
        # like, if a str is unresolved, we don't want to start cleaning up!
        # our issue is probably in the protocol.

        # these are the fields we DEFINITELY need established before even
        # ATTEMPTING to build a class.
        required_fields = \
            {f.name for f in cls._TD_FIELDS.values() if f.default is MISSING}
        required_fields -= {*cls._TD_WITHOUTS.keys()}
        required_fields -= {*cls._TD_DEFAULTS.keys()}

        filled_fields = {*init_kwargs.keys(), *init_kwarg_tasks.keys()}

        neglected_fields = required_fields - filled_fields
        if neglected_fields:
            raise TypeError(f"Fields required for {cls.__qualname__} weren't "
                            f"provided: {neglected_fields}")

        # here, we resolve our tasks to see if anything required ended up
        # not getting resolved.
        if init_kwarg_tasks:
            init_kwarg_tasks = dict(zip(
                init_kwarg_tasks.keys(),
                await asyncio.gather(*init_kwarg_tasks.values())
            ))
            init_kwargs.update(init_kwarg_tasks)

        init_kwargs = {k: v for k, v in init_kwargs.items() if v is not None}

        unresolved_fields = required_fields - {*init_kwargs.keys()}
        if unresolved_fields:
            raise TypeError(f"Fields required for {cls.__qualname__} couldn't "
                            f" be resolved: {unresolved_fields}")

        # then: make an unsafe version of the class for withouts/default facs
        # (we have to resolve all these async args here)
        all_nones = {k: None for k in cls._TD_FIELDS if k not in init_kwargs}
        instance = cls(**all_nones, **init_kwargs)

        # then: if any "without"s are unaccounted for, run those.
        ran_without = False
        for name, without in cls._TD_WITHOUTS.items():
            if name in init_kwargs:
                continue

            ran_without = True

            params = inspect.signature(without).parameters

            if run_withouts:
                if 'raw' in params:
                    result = without(instance, raw=kwargs.get(name))
                else:
                    result = without(instance)

                if asyncio.iscoroutine(result):
                    result = await result
            else:
                break

        # if we DID run a "without", we can't resolve the object
        if ran_without:
            # TODO: probably add an error here
            return None


        # then: if any "default_factory" fields are unaccounted for,
        #       run those and crash if they don't return an expected value
        for name, default_factory in cls._TD_DEFAULTS.items():
            if name in init_kwargs:
                continue

            if default_factory.from_decorator:
                params = inspect.signature(default_factory.f).parameters

                if 'raw' in params:
                    result = default_factory.f(instance, raw=kwargs.get(name))
                else:
                    result = default_factory.f(instance)
            else:
                result = default_factory.f() # type: ignore

            if asyncio.iscoroutine(result):
                result = await result

            # we allow the function itself to set self.name, or we allow
            # the function to return the value as a result
            if not getattr(instance, name, None):
                if result is None:
                    # TODO: probably add an error here
                    return None
                setattr(instance, name, result)

        return instance
