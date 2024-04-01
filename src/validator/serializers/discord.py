import disnake

from dataclasses import dataclass
from typing import Optional, Type

from ..serializer import Serializer, Serializable

@dataclass
class GuildSerializer(Serializer[disnake.Guild]):
    bot: disnake.Client

    def supports(self, Target: type) -> bool:
        return issubclass(Target, disnake.Guild)

    async def serialize(self, obj: disnake.Guild, _) -> Optional[Serializable]:
        if not isinstance(obj, disnake.Guild):
            return None
        return obj.id

    async def deserialize(self, obj: Serializable, _) -> Optional[disnake.Guild]:
        if not isinstance(obj, int):
            return None

        # should be cached
        if (guild := self.bot.get_guild(obj)):
            return guild

        # otherwise, we can fetch it
        guild = await self.bot.fetch_guild(obj)
        if not guild:
            return None

        await guild.fetch_channels()
        return guild

@dataclass
class UserSerializer(Serializer[disnake.abc.User]):
    bot: disnake.Client

    def supports(self, Target: type) -> bool:
        return issubclass(Target, disnake.User)

    async def serialize(self, obj: disnake.abc.User, _) -> Optional[Serializable]:
        if isinstance(obj, disnake.abc.User):
            return obj.id
        return None

    async def deserialize(self, obj: Serializable, _) -> Optional[disnake.User]:
        if not isinstance(obj, int):
            return None

        # should be cached
        if (user := self.bot.get_user(obj)):
            return user

        # otherwise, we can fetch it
        return await self.bot.fetch_user(obj)

@dataclass
class ChannelSerializer(Serializer[disnake.abc.GuildChannel]):

    def supports(self, Target: type) -> bool:
        return issubclass(Target, disnake.abc.GuildChannel)

    async def serialize(self,
                        obj: disnake.abc.GuildChannel,
                        Target: Type[disnake.abc.GuildChannel]) -> Optional[Serializable]:
        if not isinstance(obj, Target):
            return None

        return f"{obj.guild.id}|{obj.id}"

    async def deserialize(self,
                          obj: Serializable,
                          Target: Type[disnake.abc.GuildChannel]) -> Optional[disnake.abc.GuildChannel]:
        if not isinstance(obj, str):
            return None

        # parse obj into two ints
        try:
            guild_id, channel_id = (int(x) for x in obj.split("|"))
        except (ValueError, TypeError):
            return None

        # parse guild
        guild = await self.deserialize_type(guild_id, disnake.Guild)
        if not guild:
            return None

        # try getting channel synchronously
        channel = guild.get_channel(channel_id)
        if channel is not None:
            if isinstance(channel, Target):
                return channel
            return None

        # we can't, try fetching it
        try:
            fetched_channel = await guild.fetch_channel(channel_id)
        except disnake.NotFound:
            return None

        if isinstance(fetched_channel, Target):
            return fetched_channel
        return None

@dataclass
class RoleSerializer(Serializer[disnake.Role]):
    def supports(self, Target: type) -> bool:
        return issubclass(Target, disnake.Role)

    async def serialize(self, obj: disnake.Role, _) -> Optional[Serializable]:
        if not isinstance(obj, disnake.Role):
            return None

        return f"{obj.guild.id}|{obj.id}"

    async def deserialize(self, obj: Serializable, _) -> Optional[disnake.Role]:
        if not isinstance(obj, str):
            return None

        # parse obj into two ints
        try:
            guild_id, role_id = (int(x) for x in obj.split("|"))
        except (ValueError, TypeError):
            return None

        # parse guild
        guild = await self.deserialize_type(guild_id, disnake.Guild)
        if not guild:
            return None

        # try getting role synchronously
        role = guild.get_role(role_id)
        if role is not None:
            return role

        # we can't, try fetching it
        return disnake.utils.get(await guild.fetch_roles(), id=role_id)

@dataclass
class MessageSerializer(Serializer[disnake.Message]):
    def supports(self, Target: type) -> bool:
        return issubclass(Target, disnake.Message)

    async def serialize(self, obj: disnake.Message, _) -> Optional[Serializable]:
        if not isinstance(obj, disnake.Message):
            return None

        if obj.guild is None:
            return None

        return f"{obj.guild.id}|{obj.channel.id}|{obj.id}"

    async def deserialize(self, obj: Serializable, _) -> Optional[disnake.Message]:
        if not isinstance(obj, str):
            return None

        # parse obj into three ints
        try:
            guild_id, channel_id, message_id = (int(x) for x in obj.split("|"))
        except (ValueError, TypeError):
            return None

        # parse guild
        guild = await self.deserialize_type(guild_id, disnake.Guild)
        if not guild:
            return None

        # get channel
        try:
            channel = guild.get_channel(channel_id) or \
                await guild.fetch_channel(channel_id)
        except (disnake.NotFound, disnake.Forbidden):
            return None

        # these channels don't have fetch_message
        if isinstance(channel, disnake.CategoryChannel):
            return None
        if isinstance(channel, disnake.ForumChannel):
            return None

        try:
            return await channel.fetch_message(message_id)
        except (disnake.NotFound, disnake.Forbidden):
            return None

def disnake_serializers(bot: disnake.Client) -> list[Serializer]:
    return [
        GuildSerializer(bot),
        UserSerializer(bot),
        ChannelSerializer(),
        RoleSerializer(),
        MessageSerializer()
    ]
