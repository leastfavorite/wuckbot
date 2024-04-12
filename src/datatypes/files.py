import disnake
from typing import Annotated

from ..validator import JsonFile, TypedDict, CategoryByName, RoleByName, \
    TextChannelByName
from .. import soundcloud

from .wip import Wip
from .sketch import Sketch

class Config(JsonFile):
    class Categories(TypedDict):
        wip: CategoryByName = CategoryByName("WIPs")
        archive: CategoryByName = CategoryByName("Archive")
        sketch: CategoryByName = CategoryByName("Sketches")

    class Channels(TypedDict):
        updates: TextChannelByName = TextChannelByName("updates")
        errors: TextChannelByName = TextChannelByName("errors")
        sketch_archive: TextChannelByName = TextChannelByName("sketch-archive")
        new_sketch: TextChannelByName = TextChannelByName("sketchpad")
        role_select: TextChannelByName = TextChannelByName("roles")

    class Roles(TypedDict):
        view_wips: RoleByName = RoleByName("view wips")
        view_archive: RoleByName = RoleByName("view archive")
        band_member: RoleByName = RoleByName("bandmate")
        administrator: RoleByName = RoleByName("admin")
        administrating: RoleByName = RoleByName("sudo")

    # note: although we technically only allow this bot to operate in one guild,
    # it's HEAVILY encouraged to never treat guild as a global. technically
    # we can remove a lot of plumbing by just referencing this guild as a
    # global, but the downside is that we lose a lot of mobility if we want
    # to support many-guilds-on-one-bot later on.
    guild: disnake.Guild

    admin: disnake.User | None = None
    channels: Channels
    categories: Categories
    roles: Roles

class Tokens(JsonFile):
    discord: str
    soundcloud: str

class State(JsonFile):
    wips: list[Wip]
    sketches: list[Sketch]
    links: dict[Annotated[disnake.User, "discord"], Annotated[soundcloud.User, "soundcloud"]]
