import json
import typing
import asyncio
from typing import NamedTuple, Callable
from inspect import signature
from typeguard import check_type, TypeCheckError

import disnake
from datetime import datetime, UTC
from disnake.ext import tasks

# Utility classes for serializing/deserializing from Json.
# Use @JsonDb.serializer and @JsonDb.deserializer to create custom converters.
# You can also use automatic serial/deserialization with JsonSerializable:
# create a class variable with a dict of strs to types.
# __init__, from_json, and to_json are implemented automatically.


# helpers
def is_optional(t):
    return typing.get_origin(t) is typing.Union and \
        type(None) in typing.get_args(t)


def typename(t):
    if typing.get_origin(t) is not None:
        return repr(t)
    return t.__qualname__


# actual stuff
class ManifestError(Exception):
    pass


class JsonDict(dict):
    def __getattr__(self, name):
        if name in self:
            return self[name]
        raise AttributeError(f"Attribute not found: {name}")

    def __setattr__(self, name, value):
        if name in self:
            self[name] = value
        else:
            raise AttributeError(f"JsonDict does not have attribute {name}.")

    def __delitem__(self, name):
        raise RuntimeError("Cannot use del on JsonDict.")

    def __delattr__(self, name):
        raise RuntimeError("Cannot use del on JsonDict.")


class JsonSerializable:
    @classmethod
    def validate_dict(cls, kwargs: dict, manifest, prior_scope=None):
        prior_scope = prior_scope or []
        ret = {}
        for key, type_ in manifest.items():
            value = kwargs.get(key)

            # if we have a nested dict entry
            if type(type_) is dict:
                ret[key] = \
                    cls.validate_dict(value, type_, prior_scope + [key])
                continue

            if key not in kwargs or kwargs[key] is None:
                if is_optional(type_):
                    ret[key] = None
                    continue
                else:
                    scope = ".".join(prior_scope + [key])
                    raise ValueError(f"Expected required value "
                                     f"{scope} in {cls.__qualname__}")
            else:
                try:
                    ret[key] = check_type(value, type_)
                except TypeCheckError:
                    scope = ".".join(prior_scope + [key])
                    raise TypeCheckError(
                        f"{scope} did not match typecheck: "
                        f"expected {repr(type_)}, got {repr(value)}")
        return JsonDict(**ret)

    def __init__(self, **kwargs):
        if not hasattr(self, "MANIFEST"):
            raise NotImplementedError(
                f"MANIFEST not defined for {type(self).__qualname__}")
        new_dict = self.validate_dict(kwargs, self.MANIFEST)
        self.__dict__.update(new_dict)

    @classmethod
    async def create(cls, **kwargs):
        ret = cls(**kwargs)

        if hasattr(ret, "on_init"):
            remaining_kwargs = \
                {k: v for (k, v) in kwargs.items() if k not in cls.MANIFEST}
            await ret.on_init(**remaining_kwargs)

        return ret

    def __eq__(self, other):
        if type(other) is not type(self):
            return False

        for item in self.MANIFEST:
            if getattr(self, item, None) != getattr(other, item, None):
                return False

        return True

    def __hash__(self):
        return hash([getattr(self, x, None) for x in self.MANIFEST])

    def __repr__(self):
        classname = type(self).__qualname__
        entries = ", ".join(f"{i}={getattr(self,i)}" for i in self.MANIFEST)
        return f"{classname}({entries})"


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(
                SingletonMeta, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class JsonDb(metaclass=SingletonMeta):
    # for non-JsonSerializable stuff, we still need a way to convert it
    # to/from JSON. here, we create a registry
    _serializers = {}
    _deserializers = {}

    # builtins
    def __init__(self, data, filename):
        self.__dict__["data"] = data
        self.__dict__["filename"] = filename

    def __getattr__(self, name):
        if name in self.data:
            return self.data[name]
        raise AttributeError(f"Attribute not found: {name}")

    def __setattr__(self, name, value):
        if name in self.data:
            self.data[name] = value
        else:
            raise AttributeError(f"JsonDb does not have attribute {name}.")

    @classmethod
    async def create(cls,
                     filename: str,
                     manifest: dict,
                     **kwargs):
        try:
            with open(filename, "r") as fp:
                data = json.load(fp)
        except FileNotFoundError:
            print(f"{filename} doesn't exist, using default...")
            data = {}

        parsed = await cls.deserialize_with_manifest(data, manifest, **kwargs)
        ret = cls(parsed, filename)

        @tasks.loop(minutes=60)
        async def _save():
            ret.save()

    def save(self):
        # TODO backups
        with open(self.filename, "w") as fp:
            json.dump(self.serialize(self.data), fp, indent=2)

    # Serialize
    @classmethod
    def serialize(cls, data):

        if type(data) in [str, int, float, bool, type(None)]:
            return data

        # parse iterables
        if type(data) in [dict, JsonDict]:
            return dict(zip(
                map(cls.serialize, data.keys()),
                map(cls.serialize, data.values())
            ))
        if type(data) is list:
            return list(map(cls.serialize, data))

        # parse external serializers
        if type(data) in cls._serializers:
            return cls._serializers[type(data)](data)

        # parse internal serializers
        if issubclass(type(data), JsonSerializable):
            if hasattr(data, "to_json"):
                return data.to_json()
            manifest = type(data).MANIFEST
            return cls.serialize_to_manifest(data, manifest)

        raise NotImplementedError(
            f"No way to serialize {typename(type(data))} ({repr(data)})")

    @classmethod
    def serialize_to_manifest(cls, data, manifest):
        ret = {}
        for attr_name, value_type in manifest.items():
            if type(value_type) is dict:
                ret[attr_name] = cls.serialize_to_manifest(
                    getattr(data, attr_name, None), value_type)
            else:
                attr = getattr(data, attr_name, None)
                ret[attr_name] = cls.serialize(attr)
        return ret

    # Deserialize
    # this and deserialize_with_manifest make up the whole of the deserialization
    # logic. deserialize takes in a data and tries to convert it to target,
    # while deserialize_with_manifest takes in a dict and a manifest of types
    # and tries to convert that dict to that manifest's specification.
    @classmethod
    async def deserialize(cls,
                          data,
                          target,
                          **kwargs):
        if data is None:
            return None

        if type(target) is dict:
            return await cls.deserialize_with_manifest(data, target, **kwargs)

        if is_optional(target):
            ty = list(filter(
                lambda x: x is not type(None), typing.get_args(target)))
            if len(ty) != 1:
                raise ManifestError(f"Unknown type: {typename(target)}")
            target = ty[0]

        TargetType = typing.get_origin(target) or target
        args = typing.get_args(target)

        if TargetType in [str, int, float, bool, type(None)]:
            if type(data) is TargetType:
                return data
            raise ManifestError(f"data {data} can't be parsed "
                                f"as {typename(TargetType)}")
        if TargetType is dict:
            if type(data) is not dict:
                raise ManifestError(f"data {data} can't be parsed "
                                    f"as {typename(TargetType)}")

            KeyType = args[0]
            ValType = args[1]

            all_keys = await asyncio.gather(
                *(cls.deserialize(k, KeyType, **kwargs)
                  for k in data.keys()))
            all_values = await asyncio.gather(
                *(cls.deserialize(v, ValType, **kwargs)
                  for v in data.values()))

            return dict(zip(all_keys, all_values))

        if TargetType is list:
            if type(data) is not list:
                raise ManifestError(f"data {data} can't be parsed "
                                    f"as {typename(TargetType)}")
            ElemType = args[0]

            all_values = await asyncio.gather(
                *(cls.deserialize(e, ElemType, **kwargs) for e in data))
            return list(all_values)

        if issubclass(TargetType, JsonSerializable):
            return await TargetType.create(
                **kwargs,
                **await cls.deserialize_with_manifest(
                    data, TargetType.MANIFEST, **kwargs))

        if TargetType in cls._deserializers.keys():
            # TODO: when serializers return lists or dicts,
            # we need to preprocess them here.
            # not necessary if type converter only messes w primitives
            if type(data) in [list, dict]:
                raise NotImplementedError("deserializing from list/dict")
            deserializer: cls.Deserializer = cls._deserializers[TargetType]
            check_type(data, deserializer.source)
            return await deserializer.f(data, **kwargs)

        raise NotImplementedError(
            f"no way to deserialize {typename(type(target))}")

    # utilizing deserialize, parses a dict according to an according manifest.
    # this is essentially a special case of deserialize
    @classmethod
    async def deserialize_with_manifest(cls,
                                        data: dict,
                                        manifest: dict,
                                        **kwargs):
        # check for orphans in JSON
        required_keys = set(
            k for (k, v) in manifest.items() if not is_optional(v))
        unused_keys = set(data.keys()) - set(manifest.keys())
        if unused_keys:
            print(f"Warning, some keys in JSON are unused: {unused_keys}")

        # clear out Nones
        data = {k: v for (k, v) in data.items() if v is not None}

        # check for required keys that aren't implemented
        unimplemented_keys = required_keys - data.keys()
        if unimplemented_keys:
            raise ValueError(
                f"Required keys are unimplemented: {unimplemented_keys}")

        # we technically get this order guaranteed to us in newer versions
        # of python--i'm still wary regardless
        manifest_keys = list(manifest.keys())

        # parse child values
        parsed_vals = await asyncio.gather(
            *(cls.deserialize(data.get(k), manifest[k], **kwargs)
              for k in manifest_keys))

        # parse
        parsed_data = dict(zip(manifest_keys, parsed_vals))
        parsed_data = {k: v for (k, v) in parsed_data.items() if v is not None}

        # check again for required keys that aren't implemented
        # now that things are parsed, some things might not resolve to objects
        unimplemented_keys = required_keys - set(parsed_data.keys())
        if unimplemented_keys:
            raise ValueError(
                f"Required keys could not be resolved: {unimplemented_keys}")

        # wrap in a JsonDict, a wrapper module used to allow dot access
        return JsonDict(**{k: parsed_data.get(k) for k in manifest.keys()})

    # DECORATORS
    # provides an @JsonDb.serializer and @JsonDb.deserializer for registering
    # serializers and deserializers.
    # serializers:
    #   def f(source: FancyType) -> JsonableType
    # deserializers:
    #   async def f(client: disnake.Client, source: JsonableType) -> FancyType
    class Deserializer(NamedTuple):
        source: type
        target: type
        f: Callable

    @classmethod
    def serializer(cls, f):
        # get type
        sig = signature(f)
        source = list(sig.parameters.values())[0].annotation
        cls._serializers[source] = f
        return f

    @classmethod
    def deserializer(cls, f):
        # get type
        sig = signature(f)
        target = sig.return_annotation
        if is_optional(target):
            ty = filter(lambda x: x is not type(None),
                        typing.get_args(target))
            if len(ty) != 1:
                raise ManifestError(f"Unknown type: {typename(target)}")
            target = ty[0]

        source = list(sig.parameters.values())[0].annotation

        cls._deserializers[target] = cls.Deserializer(
            source=source,
            target=target,
            f=f)
        return f

    # TODO: some signature magic can get rid of these **_s

class Secrets(JsonDb):
    pass
class State(JsonDb):
    pass


# Serializers
# @JsonDb.deserializer
# async def deserialize(client: disnake.Client, data: str) -> disnake.Message:
#     # pass
#
# def serialize(obj: disnake.Message) -> str

# disnake.User
@JsonDb.deserializer
async def deserialize(id_: int, /, bot: disnake.Client, **_) -> disnake.User:
    return bot.get_user(id_) or await bot.fetch_user(id_)


@JsonDb.serializer
def serialize(user: disnake.User) -> int:
    return user.id


# disnake.TextChannel
@JsonDb.deserializer
async def deserialize(chan: str, /, bot: disnake.Client, **_) -> \
        disnake.TextChannel:
    guild_id, channel_id = [int(x, 10) for x in chan.split("|")]
    guild = bot.get_guild(guild_id)
    if guild is None:
        return None
    try:
        return guild.get_channel(channel_id) or \
            await guild.fetch_channel(channel_id)
    except (disnake.NotFound, disnake.Forbidden):
        return None


@JsonDb.serializer
def serialize(chan: disnake.TextChannel) -> str:
    return f"{chan.guild.id}|{chan.id}"


# disnake.Role
@JsonDb.deserializer
async def deserialize(role: str, /, bot: disnake.Client, **_) -> disnake.Role:
    guild_id, role_id = [int(x, 10) for x in role.split("|")]
    guild = bot.get_guild(guild_id)
    if guild is None:
        return None
    return guild.get_role(role_id) or \
        disnake.utils.get(await guild.fetch_roles(), id=role_id)


@JsonDb.serializer
def serialize(role: disnake.Role) -> str:
    return f"{role.guild.id}|{role.id}"


# disnake.Message
@JsonDb.deserializer
async def deserialize(msg: str, /, bot: disnake.Client, **_) -> \
        disnake.Message:
    guild_id, channel_id, msg_id = [int(x, 10) for x in msg.split("|")]
    guild = bot.get_guild(guild_id)
    if guild is None:
        return None
    try:
        channel = guild.get_channel(channel_id) or \
            await guild.fetch_channel(channel_id)
        return await channel.fetch_message(msg_id)
    except (disnake.NotFound, disnake.Forbidden):
        return None


@JsonDb.serializer
def serialize(msg: disnake.Message) -> str:
    return f"{msg.guild.id}|{msg.channel.id}|{msg.id}"


# datetime.datetime
@JsonDb.deserializer
async def deserialize(dt: int, **_) -> datetime:
    return datetime.fromtimestamp(dt, UTC)


@JsonDb.serializer
def serialize(dt: datetime) -> int:
    return int(dt.timestamp())

