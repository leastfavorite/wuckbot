import inspect
import asyncio

from typing import Type, TypeVar, Generic, TypeAlias, Union, Optional, Callable, Awaitable, Any
from dataclasses import dataclass
from typeguard import check_type

from .serializer import BaseSerializer, Serializable

T = TypeVar('T')
Without: TypeAlias = \
    Union[Callable[['TypedDict', Serializable], None],
          Callable[['TypedDict', Serializable], Awaitable[None]]]

Default: TypeAlias = \
    Union[Callable[['TypedDict'], Optional[T]],
          Callable[['TypedDict'], Awaitable[Optional[T]]]]


class MissingType:
    pass
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

class TypedDictMeta(type):
    def __new__(mcs, name, bases, attrs):
        cls = super().__new__(mcs, name, bases, attrs)
        cls._TD_FIELDS = {}
        cls._TD_WITHOUTS = {}
        cls._TD_DEFAULTS = {}

        # find any fields in base classes
        for base in cls.__mro__[-1:0:-1]:
            for field_name, field in getattr(base, "_TD_FIELDS", {}):
                cls._TD_FIELDS[field_name] = TdField(
                    name=field.name,
                    type=field.type,
                    default=field.default
                )
            cls._TD_WITHOUTS.update(getattr(base, "_TD_WITHOUTS", {}))
            cls._TD_DEFAULTS.update(getattr(base, "_TD_DEFAULTS", {}))

        # find our own fields
        cls_annotations = inspect.get_annotations(cls)
        for name, type in cls_annotations.items():
            default = getattr(cls, name, MISSING)
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

                if field_name in cls._TD_DEFAULTS:
                    del cls._TD_DEFAULTS[field_name]
                cls._TD_DEFAULTS[field_name] = attr

        return cls

    # True if all fields have a default or default_factory
    @property
    def has_default(cls):
        needs_factory = {
            f.name for f in cls._TD_FIELDS.values() if f.default is MISSING}
        factories = {cls._TD_DEFAULTS.keys()}
        return len(needs_factory - factories) == 0


# TODO: __eq__, __hash__, __repr__
class TypedDict(metaclass=TypedDictMeta):

    _TD_FIELDS: dict[str, TdField] = {}
    _TD_WITHOUTS: dict[str, Without] = {}
    _TD_DEFAULTS: dict[str, Default] = {}

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    @classmethod
    async def create(cls, **kwargs):
        return await cls._create(check_type, False, **kwargs)

    Coerce: TypeAlias = Union[
        Callable[[Any, Type[T]], Optional[T]],
        Callable[[Any, Type[T]], Awaitable[Optional[T]]]]

    # a more general version of _create. allows an arbitrary
    # function to coerce input values into their required types.
    # substituting type_check for a data deserialization scheme, for instance,
    # allows us to deserialize kwargs with the same logic we use to instantiate
    @classmethod
    async def _create(cls, coerce: Coerce, run_withouts=False, /, **kwargs):
        coerce_is_async = inspect.iscoroutinefunction(coerce)

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
            else:
                if field.default is not MISSING:
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
        all_nones = {k: None for k in cls._TD_FIELDS}
        instance = cls(**all_nones, **init_kwargs)

        # then: if any "without"s are unaccounted for, run those.
        ran_without = False
        for name, without in cls._TD_WITHOUTS.items():
            if name in init_kwargs:
                continue

            ran_without = True
            if run_withouts:
                if asyncio.iscoroutinefunction(without):
                    await without(instance, kwargs.get(name))
                else:
                    without(instance, kwargs.get(name))
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

            if asyncio.iscoroutinefunction(default_factory):
                # we don't create_task here because we assume
                # default_factories depend on previous values, and that
                # order matters
                result = await default_factory(instance)
            else:
                result = default_factory(instance)

            # we allow the function itself to set self.name, or we allow
            # the function to return the value as a result
            if not getattr(instance, name, None):
                if result is None:
                    # TODO: probably add an error here
                    return None
                setattr(instance, name, result)

        return instance
