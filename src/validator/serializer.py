from typing import Type, Optional, Union, Any, TypeAlias, TypeVar, Generic
import typing

Serializable: TypeAlias = Union[str, int, float, bool, None,
                                list['Serializable'],
                                tuple['Serializable'],
                                dict[str, 'Serializable']]


def strip_optional(T: type):
    if typing.get_origin(T) is Union and type(None) in typing.get_args(T):
        for BaseType in typing.get_args(T):
            if BaseType is not type(None):
                return BaseType
    return T

def typename(t):
    if typing.get_origin(t) is not None:
        return repr(t)
    return t.__qualname__


T = TypeVar('T')
class BaseSerializer(Generic[T]):
    def supports(self, Target: type) -> bool:
        raise NotImplementedError()

    async def serialize(self, obj: T, Target: Type[T]) -> Serializable:
        raise NotImplementedError()

    async def deserialize(
            self, s: Serializable, Target: Type[T]) -> Optional[T]:
        raise NotImplementedError()

U = TypeVar('U')
class Serializer(BaseSerializer[T]):
    def __init__(self, *args, **kwargs):
        self.registrar = None
        super().__init__(*args, **kwargs)

    async def serialize_type(self, obj: U, Target: type[U]) -> Serializable:
        if self.registrar:
            return await self.registrar.serialize(obj, Target)
        else:
            raise RuntimeError(
                "serialize_type called on unregistered serializer")

    async def deserialize_type(
            self, obj: Serializable, Target: type[U]) -> Optional[U]:
        if self.registrar:
            return await self.registrar.deserialize(obj, Target)
        else:
            raise RuntimeError(
                "deserialize_type called on unregistered serializer")


class Registrar(BaseSerializer[Any]):
    def __init__(self, *serializers: Serializer):
        self.serializers: list[Serializer] = []
        self.register(*serializers)

    def supports(self, Target: type) -> bool:
        Target = strip_optional(Target)
        return any(v.supports(Target) for v in self.serializers)

    async def deserialize(
            self, s: Serializable, Target: Type[T]) -> Optional[T]:
        Target = strip_optional(Target)
        for serializer in self.serializers:
            if serializer.supports(Target):
                return await serializer.deserialize(s, Target)
        raise NotImplementedError(f"No way to deserialize {typename(Target)}")

    async def serialize(self, obj: T, Target: Type[T]) -> Serializable:
        Target = strip_optional(Target)
        for serializer in self.serializers:
            if serializer.supports(Target):
                return await serializer.serialize(obj, Target)
        raise NotImplementedError(f"No way to serialize {typename(Target)}")

    def register(self, *serializers: Serializer):
        for s in serializers:
            self.serializers.append(s)
            s.registrar = self
        pass
