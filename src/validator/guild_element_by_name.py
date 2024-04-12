import disnake

from typing import TypeVar, Generic
from dataclasses import dataclass

from ..utils import UserError

T = TypeVar('T')
@dataclass
class GuildElementByName(Generic[T]):
    name: str

    @property
    def ELEM_LIST(self):
        raise NotImplementedError()

    @property
    def TARGET_NAME(self):
        raise NotImplementedError()

    async def fetch(self):
        pass

    async def get(self, guild: disnake.Guild) -> T:
        elems = getattr(guild, self.ELEM_LIST)
        if (elem := disnake.utils.get(elems, name=self.name)):
            return elem

        await self.fetch()

        elems = getattr(guild, self.ELEM_LIST)
        if (elem := disnake.utils.get(elems, name=self.name)):
            return elem

        raise UserError(
            f"Couldn't find {self.TARGET_NAME} called '{self.name}'.")

class CategoryByName(GuildElementByName[disnake.CategoryChannel]):
    ELEM_LIST = "categories"
    TARGET_NAME = "a channel category"
    async def fetch(self):
        await self.guild.fetch_channels()

class TextChannelByName(GuildElementByName[disnake.TextChannel]):
    ELEM_LIST = "text_channels"
    TARGET_NAME = "a text channel"
    async def fetch(self):
        await self.guild.fetch_channels()

class RoleByName(GuildElementByName[disnake.Role]):
    ELEM_LIST = "roles"
    TARGET_NAME = "a role"
    async def fetch(self):
        await self.guild.fetch_roles()
