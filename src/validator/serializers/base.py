import typing
import asyncio
import inspect

from datetime import datetime, UTC
from typing import Optional, Type, TypeVar, Annotated

from ..typed_dict import TypedDict
from ..serializer import Serializer, Serializable

class IdentitySerializer(Serializer[Serializable]):
    def supports(self, Target: type) -> bool:
        return Target in [str, int, float, bool, None, type(None)]

    async def serialize(self, obj: Serializable, Target: type):
        if isinstance(obj, Target):
            return obj
        return None

    async def deserialize(self, obj: Serializable, Target: type):
        if isinstance(obj, Target):
            return obj
        return None

class ListSerializer(Serializer[list]):
    def supports(self, Target: type) -> bool:
        return typing.get_origin(Target) is list

    async def serialize(self, obj: list, Target: Type[list]) -> Optional[Serializable]:
        if not isinstance(obj, list):
            return None

        InnerType = typing.get_args(Target)[0]
        serialized = await asyncio.gather(
            *(self.serialize_type(x, InnerType) for x in obj))
        return [x for x in serialized if x is not None]

    async def deserialize(self, obj: Serializable, Target: Type[list]) -> Optional[list]:
        if not isinstance(obj, list):
            return None

        InnerType = typing.get_args(Target)[0]
        deserialized = await asyncio.gather(
            *(self.deserialize_type(x, InnerType) for x in obj))
        return [x for x in deserialized if x is not None]

class TupleSerializer(Serializer[tuple]):
    def supports(self, Target: type) -> bool:
        return typing.get_origin(Target) is tuple

    async def serialize(self, obj: tuple, Target: Type[tuple]) -> Optional[Serializable]:
        if not isinstance(obj, tuple):
            return None

        InnerType = typing.get_args(Target)[0]
        serialized = await asyncio.gather(
            *(self.serialize_type(x, InnerType) for x in obj))
        return list(serialized)

    async def deserialize(self, obj: Serializable, Target: Type[tuple]) -> Optional[tuple]:
        if not isinstance(obj, list):
            return None

        InnerType = typing.get_args(Target)[0]
        deserialized = await asyncio.gather(
            *(self.deserialize_type(x, InnerType) for x in obj))
        return tuple(deserialized)

T = TypeVar('T')
class StrDictSerializer(Serializer[dict[str, T]]):
    def supports(self, Target: type) -> bool:
        return typing.get_origin(Target) is dict \
            and typing.get_args(Target)[0] is str

    async def serialize(self, obj: dict[str, T], Target: Type[dict]) -> Optional[Serializable]:
        if not isinstance(obj, dict):
            return None

        for key in obj.keys():
            if not isinstance(key, str):
                return None

        InnerType = typing.get_args(Target)[1]
        values = await asyncio.gather(
            *(self.serialize_type(x, InnerType) for x in obj.values()))

        result = dict(zip(obj.keys(), values))
        return {k: v for k, v in result.items() if v is not None}

    async def deserialize(self, obj: Serializable, Target: Type[dict]) -> Optional[dict]:
        if not isinstance(obj, dict):
            return None

        InnerType = typing.get_args(Target)[1]
        values = await asyncio.gather(
            *(self.deserialize_type(x, InnerType) for x in obj.values()))

        result = dict(zip(obj.keys(), values))
        return {k: v for k, v in result.items() if v is not None}

K = TypeVar('K')
V = TypeVar('V')
class DictSerializer(Serializer[dict[K, V]]):
    def supports(self, Target: type) -> bool:
        return typing.get_origin(Target) is dict \
            and typing.get_args(Target)[0] is not str

    async def serialize(self, obj: dict, Target: Type[dict]) -> Optional[Serializable]:

        if not isinstance(obj, dict):
            return None
        k = typing.get_args(Target)[0]
        k_name = "key"
        v = typing.get_args(Target)[0]
        v_name = "value"

        if k is Annotated:
            k = typing.get_args(k)[0]
            k_name = typing.get_args(k)[1]
        if v is Annotated:
            v = typing.get_args(v)[0]
            v_name = typing.get_args(v)[1]

        ks = list(await asyncio.gather(
            *(self.serialize_type(x, k) for x in obj.keys())))
        vs = list(await asyncio.gather(
            *(self.serialize_type(x, v) for x in obj.values())))

        return {
            k_name: ks,
            v_name: vs
        }

    async def deserialize(self, obj: Serializable, Target: Type[dict]) -> Optional[dict]:
        if not isinstance(obj, dict):
            return None

        k = typing.get_args(Target)[0]
        k_name = "key"
        v = typing.get_args(Target)[0]
        v_name = "value"

        if k is Annotated:
            k = typing.get_args(k)[0]
            k_name = typing.get_args(k)[1]
            if not isinstance(k_name, str):
                raise ValueError("Annotated was given a non-string")
        if v is Annotated:
            v = typing.get_args(v)[0]
            v_name = typing.get_args(v)[1]
            if not isinstance(v_name, str):
                raise ValueError("Annotated was given a non-string")

        if k_name not in obj:
            return None
        if v_name not in obj:
            return None

        ks = obj.get(k_name, [])
        vs = obj.get(v_name, [])
        if not isinstance(ks, list):
            return None
        if not isinstance(vs, list):
            return None

        ks = list(
            await asyncio.gather(*(self.serialize_type(x, k) for x in ks)))
        vs = list(
            await asyncio.gather(*(self.serialize_type(x, v) for x in vs)))

        return {k: v for k, v in zip(ks, vs) if k is not None and v is not None}

class TypedDictSerializer(Serializer[TypedDict]):
    def supports(self, Target: type) -> bool:
        return inspect.isclass(Target) and issubclass(Target, TypedDict)

    async def serialize(self, obj: TypedDict, Target: Type[TypedDict]) -> Optional[Serializable]:
        if not isinstance(obj, Target):
            return None

        values = await asyncio.gather(
            *(self.serialize_type(getattr(obj, name, None), field.type)
              for name, field in Target._TD_FIELDS.items()))

        result = dict(zip(Target._TD_FIELDS.keys(), values))
        return {k: v for k, v in result.items() if v is not None}

    async def deserialize(self, obj: Serializable, Target: Type[TypedDict]) -> Optional[TypedDict]:
        if not isinstance(obj, dict):
            return None

        return await Target._create(self.deserialize_type, True, **obj)

class DatetimeSerializer(Serializer[datetime]):
    def supports(self, Target: type) -> bool:
        return issubclass(Target, datetime)

    async def serialize(self, obj: datetime, _) -> Optional[Serializable]:
        return int(obj.timestamp())

    async def deserialize(self, obj: Serializable, _) -> Optional[datetime]:
        if not isinstance(obj, int):
            return None
        return datetime.fromtimestamp(obj, UTC)

def base_serializers() -> list[Serializer]:
    return [
        IdentitySerializer(),
        ListSerializer(),
        TupleSerializer(),
        DatetimeSerializer(),
        DictSerializer(),
        TypedDictSerializer(),
    ]
