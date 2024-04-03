import disnake
import asyncio
from typing import Optional, Annotated, Union
from datetime import datetime

from ..validator import TypedDict, without, default
from ..utils.errors import UserError, send_error
from ..utils import embeds, buttons, get_blame, Blamed, get_collaborators
from .. import soundcloud, state

class Update(TypedDict):
    file: Optional[disnake.Message] = None
    message: disnake.Message
    timestamp: datetime

    # TODO
    @without("message")
    async def without_message(self):
        pass

    # TODO
    @without("track")
    async def without_track(self):
        pass

class Credit(TypedDict):
    producers: Annotated[list[disnake.User], list]
    vocalists: Annotated[list[disnake.User], list]

class Wip(TypedDict):
    # metadata
    name: str
    progress: int
    credit: Annotated[Credit, Credit.create]

    # discord stuff
    guild: disnake.Guild
    channel: disnake.TextChannel
    role: disnake.Role
    pinned: disnake.Message

    track: Optional[soundcloud.Track] = None

    # most recent update (if it exists)
    update: Optional[Update] = None

    # timestamp
    timestamp: Annotated[datetime, disnake.utils.utcnow]

    @without("guild")
    async def without_guild(self):
        raise TypeError("Guild not provided in WIP. Maybe I got kicked?")

    @without("channel")
    async def without_channel(self, *,
                              raw: str | None = None,
                              author: Blamed = None):
        if not self.guild:
            # we've got bigger fish to fry
            return

        if raw and not author:
            _, channel_id = [int(x) for x in raw.split("|")]

            # don't do anything if we deleted the channel
            author = await get_blame(
                guild=self.guild,
                action=disnake.AuditLogAction.channel_delete,
                target_id=channel_id)

        if author and author.id == self.guild.me.id:
            return

        # deletes role
        if self.role:
            await self.role.delete()

        embed = embeds.error(
            msg="Please don't delete WIP channels. If you don't want to work "
                "on a song anymore, use `/archive` instead.",
            title=f"WIP Channel '{self.name}' Deleted")
        components = [buttons.track_delete(self.track)] if self.track else None
        content = author.mention if author else ""

        await send_error(
            guild=self.guild,
            content=content,
            embed=embed,
            components=components)

    @default("role")
    async def reconstruct_role(self, *,
                               raw: str | None = None,
                               author: Blamed = None):
        if raw and not author:
            _, role_id = [int(x) for x in raw.split("|")]

            # don't do anything if we deleted the channel
            author = await get_blame(
                guild=self.guild,
                action=disnake.AuditLogAction.role_delete,
                target_id=role_id)

        if author and author.id == self.guild.me.id:
            return

        self.role = await self.guild.create_role(
            name=self.name,
            permissions=disnake.Permissions.none(),
            mentionable=True,
            reason="role reconstruction for WIP")

        await send_error(
            guild=self.guild,
            content=author.mention if author else "",
            embed=embeds.error(
                msg="Please don't delete WIP roles. If you don't want to work "
                    "on a song anymore, use `/archive` instead.",
                title=f"WIP Role '{self.name}' Deleted"
            ),
            components = [buttons.wip_join(self)]
        )

    @default("pinned")
    async def update_pinned(self):
        if self.pinned is None:
            self.pinned = await self.channel.send(embed=self.pinned_embed())
        else:
            await self.pinned.edit(embed=self.pinned_embed())

        if not self.pinned.pinned:
            await self.pinned.pin()

    @staticmethod
    def _get_channel_name(name: str, progress: int):
        s = [
            "\N{BLACK LARGE SQUARE}",
            "\N{LARGE RED SQUARE}",
            "\N{LARGE ORANGE SQUARE}",
            "\N{LARGE YELLOW SQUARE}",
            "\N{LARGE GREEN SQUARE}",
        ]
        w = "\N{WHITE LARGE SQUARE}"

        bars_raw = [[s[i]+s[0]+s[0], w+s[i]+s[0], w+w+s[i]] for i in range(len(s))]
        bars_transposed = zip(*bars_raw)  # transpose
        bars = [x for list_ in bars_transposed for x in list_]  # flatten
        bars.append("\U00002B50\U0001F389\U0001F973")

        bar = bars[(len(bars)-1)*progress//100]

        return f"{bar}-{name.lower().replace(' ', '-')}"

    @staticmethod
    def _validate_name(name: str, guild: disnake.Guild):
        if disnake.utils.get(state().wips, name=name) is not None:
            raise UserError(
                f"Another WIP already uses the name \"{name}\".")

        if disnake.utils.get(guild.roles, name=name) is not None:
            raise UserError(
                f"A role in this server already uses the name \"{name}\".")

    @staticmethod
    def _validate_progress(progress: Union[str, int]) -> int:
        if isinstance(progress, str):
            progress_text = progress
            try:
                progress = int(progress_text.rstrip("%"), 10)
            except ValueError:
                raise UserError(
                    f"Could not parse {progress} as a percentage.")
        if progress < 0 or progress > 100:
            raise UserError(f"Could not parse {progress} as a percentage.")
        return progress

    @classmethod
    async def from_channel(
            cls, *,
            name: str,
            progress: Union[str, int],
            track: Optional[soundcloud.Track] = None,
            existing_channel: Optional[disnake.TextChannel] = None,
            extra_members: Optional[list[disnake.Member]] = None):

        # get guild
        guild = None
        if existing_channel:
            guild = existing_channel.guild
        elif extra_members:
            guild = extra_members[0].guild

        if not guild:
            raise ValueError("Must specify either a channel or extra members")

        # validate inputs
        cls._validate_name(name, guild)
        progress = cls._validate_progress(progress)

        if existing_channel:
            if disnake.utils.get(state().wips, channel=existing_channel):
                raise UserError("This channel is already a WIP.")

        # get WIPs category
        if not (category := disnake.utils.get(guild.categories, name="WIPs")):
            raise UserError("Could not find a channel category called WIPs.")

        # roles that are specifically denied access
        # TODO: specific role name should be specifiable in config
        if not (webcage := disnake.utils.get(guild.roles, name="webcage")):
            raise UserError("Couldn't find a role called 'webcage'")

        # roles that are allowed access
        # TODO: specific role name should be specifiable in config
        if not (view_wips := disnake.utils.get(guild.roles, name="view wips")):
            raise UserError("Couldn't find a role called 'view wips'")

        # create new role for allowing access
        new_role = await guild.create_role(
            name=name,
            permissions=disnake.Permissions.none(),
            mentionable=True,
            reason="/wipify")

        members = set(extra_members if extra_members else [])

        if existing_channel:
            # keep sketches from simultaneously being WIPs
            state().sketches = [
                s for s in state().sketches if s.channel != existing_channel]

            # add anyone who has sent an audio file
            members.update(await get_collaborators(existing_channel))

        await asyncio.gather(
            *(m.add_roles(new_role, reason="/wipify") for m in members))

        access_roles: set[Union[disnake.Member, disnake.Role]] = {view_wips, new_role, guild.me}
        deny_roles: set[Union[disnake.Member, disnake.Role]] = {webcage, guild.default_role}

        kwargs = {
            "name": cls._get_channel_name(name, progress),
            "topic": "Use /wip to update this WIP",
            "reason": "/wipify",
            "category": category,
            "position": 0,
            "overwrites": {
                **{role: disnake.PermissionOverwrite(view_channel=True)
                   for role in access_roles},
                **{role: disnake.PermissionOverwrite(view_channel=False,
                                                     manage_channels=False)
                   for role in deny_roles}
            }
        }

        if existing_channel:
            await existing_channel.edit(**kwargs)
            channel = existing_channel
        else:
            channel = await guild.create_text_channel(**kwargs)

        # create the wip
        wip = await Wip.create(
            name=name,
            progress=progress,
            guild=guild,
            channel=channel,
            role=new_role)
        state().wips.append(wip)
        await state().save()

        return wip

    def view_embed(self):
        return self.as_embed(
            title_prefix="",
            include_links=True,
            use_update_timestamp=True,
            show_help=False)

    def update_embed(self):
        return self.as_embed(
            title_prefix="\N{BELL}",
            include_links=False,
            use_update_timestamp=False,
            show_help=False)

    def pinned_embed(self):
        return self.as_embed(
            title_prefix="\N{PUSHPIN}",
            include_links=True,
            use_update_timestamp=True,
            show_help=True)

    def archive_embed(self):
        embed = self.as_embed(
            title_prefix="\N{OPEN FILE FOLDER}",
            include_links=True,
            use_update_timestamp=True,
            show_help=False)
        embed.color = disnake.Color.yellow()
        embed.description = "This WIP has been archived."
        return embed

    def as_embed(self, *,
                 title_prefix: str,
                 include_links: bool,
                 use_update_timestamp: bool,
                 show_help: bool):

        embed = disnake.Embed(
            color=disnake.Color.blue(),
            title=f"{title_prefix} {self.name} ({self.progress}%)"
        )

        # set timestamp.
        # we use the "created at" timestamp unless specified otherwise
        if self.update and use_update_timestamp:
            embed.timestamp = self.update.timestamp
            embed.set_footer(
                text="last update",
                icon_url=embeds.WUCK
            )
        else:
            embed.timestamp = self.timestamp
            embed.set_footer(text="created on", icon_url=embeds.WUCK)

        # set up credit
        if show_help:
            vocalists = "nobody\n(try `/wip credit vocalist`)"
            producers = "nobody\n(try `/wip credit producer`)"
        else:
            vocalists = "nobody"
            producers = "nobody"

        if self.credit.vocalists:
            vocalists = "\n".join(
                map(lambda a: a.mention, self.credit.vocalists))
        if self.credit.producers:
            producers = "\n".join(
                map(lambda a: a.mention, self.credit.producers))

        embed.add_field(name="featuring:", value=vocalists, inline=True)
        embed.add_field(name="produced by:", value=producers, inline=True)

        if not include_links:
            return embed

        # create links
        links = []
        if self.update:
            links.append(f"[last update]({self.update.message.jump_url})")
        if self.track:
            links.append(f"[soundcloud]({self.track.url})")

        if links:
            embed.add_field(
                name="links:", value="\n".join(links), inline=False)

        return embed

    def soundcloud_description(self):
        linked_users = {x.discord: x.sc for x in state().links}

        vocalists = self.credit.vocalists
        vocalists = (v for v in vocalists if v in linked_users)
        vocalists = ["@" + linked_users[v].permalink for v in vocalists]
        vocalists = vocalists or ["nobody"]

        producers = self.credit.producers
        producers = (p for p in producers if p in linked_users)
        producers = ["@" + linked_users[p].permalink for p in producers]
        producers = producers or ["nobody"]

        return "\n".join(
            ["featuring:", *vocalists, "\nproduced by:", *producers])

    def unlinked_members(self):
        members = set(*self.credit.vocalists, *self.credit.producers)
        linked = set(x.discord for x in state().links)
        return members - linked

    async def edit(self, *,
                   name: Optional[str] = None,
                   progress: Optional[Union[str, int]] = None):

        if name is not None:
            # check for name collision
            if self.name == name:
                raise UserError(f"This WIP is already called `{name}`.")
            self._validate_name(name, self.guild)

        if progress is not None:
            progress = self._validate_progress(progress)

        self.name = name or self.name
        self.progress = progress or self.progress

        new_name = self._get_channel_name(self.name, self.progress)
        if self.channel.name != new_name:
            await self.channel.edit(name=new_name)

        if self.update:
            await self.update.message.edit(embed=self.update_embed())

        if self.track:
            await self.track.edit(
                title=name,
                description=self.soundcloud_description()
            )

        await self.update_pinned()
