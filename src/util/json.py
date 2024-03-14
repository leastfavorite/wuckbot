import json
import disnake
import asyncio
from typing import Any
from types import SimpleNamespace
from collections import namedtuple

_from_json = {}
_to_json = {}


# helpers
async def amap(f, iter_):
    return list(await asyncio.gather(*map(f, iter_)))


async def admap(f, dict_):
    return dict(zip(dict_.keys(),
                    await asyncio.gather(*map(f, dict_.values()))))


async def dmap(f, dict_):
    return dict(zip(dict_.keys(), map(f, dict_.values())))


# mark a class as "able to be turned into JSON"
class JsonSerializable:

    def to_json(self):
        raise NotImplementedError(
            "JsonSerializer has not implemented to_json")

    @classmethod
    async def from_json(cls, client: disnake.Client, data: Any):
        raise NotImplementedError(
            "JsonSerializer has not implemented from_json")


class JsonSerializer:
    @staticmethod
    def get_json_type() -> type:
        raise NotImplementedError(
            "JsonSerializer has not implemented get_json_type")

    @staticmethod
    def to_json(obj):
        raise NotImplementedError(
            "JsonSerializer has not implemented to_json")

    @staticmethod
    async def from_json(client: disnake.Client, data: Any):
        raise NotImplementedError(
            "JsonSerializer has not implemented from_json")


def register_serializer(cls, stored_name=None):
    stored_name = stored_name or cls.__qualname__
    if issubclass(cls, JsonSerializable):
        _from_json[stored_name] = cls
    elif issubclass(cls, JsonSerializer):
        target_type = cls.get_json_type()
        _from_json[stored_name] = cls
        _to_json[target_type] = cls
    else:
        raise ValueError(f"{cls.__qualname__} could not be registered")


class MessageSerializer(JsonSerializer):
    @staticmethod
    def get_json_type():
        return disnake.Message

    @staticmethod
    def to_json(obj: disnake.Message):
        return {
            "guild": obj.guild.id,
            "channel": obj.channel.id,
            "message": obj.id
        }

    @staticmethod
    async def from_json(client: disnake.Client, data: dict[str, int]):
        guild = client.get_guild(data["guild"])
        if guild is None:
            return None
        channel = guild.get_channel(data["channel"])
        if channel is None:
            channel = await guild.fetch_channel(data["channel"])
            if channel is None:
                return None
        message = await channel.fetch_message(data["message"])
        if message is None:
            return None


class RoleSerializer(JsonSerializer):
    @staticmethod
    def get_json_type():
        return disnake.Role

    @staticmethod
    def to_json(obj: disnake.Message):
        return {
            "guild": obj.guild.id,
            "role": obj.id
        }

    @staticmethod
    async def from_json(client: disnake.Client, data: dict[str, int]):
        guild = client.get_guild(data["guild"])
        if guild is None:
            return None
        role = guild.get_role(data["role"])
        if role is None:
            await guild.fetch_roles()
            role = guild.get_role(data["role"])
            if role is None:
                return None


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(
                SingletonMeta, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class JsonDb(metaclass=SingletonMeta):

    def __init__(self, parsed_data: dict, filename: str):
        self._data = parsed_data
        self._filename = filename

    @classmethod
    async def _deserialize(cls, client: disnake.Client, data: Any):
        if type(data) is list:
            # for lists, parse all child elements and return as list
            return await amap(lambda x: cls._deserialize(client, x), data)

        if type(data) is dict:
            # validate incoming dict
            if "type" not in data:
                raise ValueError(f"dict present without type: {data}")
            if "data" not in data:
                raise ValueError(f"dict present without data: {data}")

            inner_data = await admap(lambda x: cls._deserialize(client, x),
                                     data["data"])

            # if the result type is a dict, we need no further processing
            if data["type"] == "dict":
                return inner_data
            else:
                # otherwise, parse the dict into the final object
                serializer = _from_json.get(data["type"])
                if not serializer:
                    raise ValueError(
                        f"Could not decode object of type {data['type']}")

                return await serializer.from_json(client, inner_data)
        else:
            # non-sequence
            return data

    @classmethod
    def _serialize(cls, data: Any):
        if isinstance(data, JsonSerializer):
            serialized = data.to_json()
        if (serializer := _to_json.get(type(data))) is not None:
            serialized = serializer.to_json(data)
        else:
            serialized = data

        if type(serialized) is dict:
            return dmap(cls._serialize, serialized)
        if type(serialized) in [list, tuple]:
            return list(map(cls._serialize, serialized))
        return serialized

    @classmethod
    async def from_file(cls, client: disnake.Client, filename: str):
        try:
            with open(filename, "r") as fp:
                raw_data = json.load(fp)
        except FileNotFoundError:
            print(f"{filename} doesn't exist, using default...")
            raw_data = {}
            if type(raw_data) is not dict:
                raise ValueError(f"Parsed JSON for {filename} was not a dict")

        parsed_data = await admap(lambda x: cls._deserialize(client, x),
                                  raw_data)
        return cls(parsed_data, filename)


register_serializer(MessageSerializer)
register_serializer(RoleSerializer)


def jsontuple(name, fields):
    ret = namedtuple(name, fields)

    class JsonTupleSerializer(JsonSerializer):
        @staticmethod
        def get_json_type():
            return ret

        @staticmethod
        def to_json(obj):
            return dict(zip(fields, obj))

        @staticmethod
        def from_json(client: disnake.Client, data: Any):
            return ret(**data)
    register_serializer(JsonTupleSerializer)

    return ret


class Secrets(JsonDb):
    pass


class State(JsonDb):
    pass
