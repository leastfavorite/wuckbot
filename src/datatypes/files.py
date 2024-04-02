from typing import Annotated, TYPE_CHECKING
import disnake

from ..validator import JsonFile, TypedDict
from .. import soundcloud

from .wip import Wip

class LinkedUser(TypedDict):
    sc: soundcloud.User
    discord: disnake.User

class State(JsonFile):
    wips: Annotated[list[Wip], list]
    links: Annotated[list[LinkedUser], list]

class Secrets(JsonFile):
    guilds: list[disnake.Guild]
    bot_token: str
    admin: disnake.User
    sc_oauth: str