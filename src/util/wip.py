import disnake
from typing import Optional, Union
from datetime import datetime

from util.json import State, JsonSerializable
from util.decorators import UserError
from util.embeds import WUCK

from util import soundcloud


class Update(JsonSerializable):
    MANIFEST = {
        "file": disnake.Message,
        "update": Optional[disnake.Message],
        "timestamp": datetime
    }


class Wip(JsonSerializable):
    # assuming we know how to serialize SoundcloudTrack, TextChannel, etc.
    # this class can now be initialized into smart, fancy datatypes from JSON
    # without any of this type information cluttering up the JSON file
    MANIFEST = {
        "name": str,
        "progress": int,
        "track": Optional[soundcloud.Track],
        "channel": disnake.TextChannel,
        "role": disnake.Role,
        "credit": {
            "producers": list[disnake.User],
            "vocalists": list[disnake.User]
        },
        "pinned": Optional[disnake.Message],
        "updates": list[Update],
        "created_timestamp": datetime
    }

    @property
    def guild(self) -> disnake.Guild:
        return self.channel.guild

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

        bars = [[s[i]+s[0]+s[0], w+s[i]+s[0], w+w+s[i]] for i in range(len(s))]
        bars = zip(*bars)  # transpose
        bars = [x for list_ in bars for x in list_]  # flatten
        bars.append("\U00002B50\U0001F389\U0001F973")

        bar = bars[(len(bars)-1)*progress//100]

        return f"{bar}-{name.lower().replace(' ', '-')}"

    @staticmethod
    def _validate_name(name: str, guild: disnake.Guild):
        if disnake.utils.get(State().wips, name=name) is not None:
            raise UserError(
                f"Another WIP already uses the name \"{name}\".")

        if disnake.utils.get(guild.roles, name=name) is not None:
            raise UserError(
                f"A role in this server already uses the name \"{name}\".")

    @staticmethod
    def _purify_progress(progress: Union[str, int]) -> int:
        if type(progress) is str:
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
    def _get_new_channel_kwargs(cls, *,
                                name: str,
                                progress: int,
                                category: disnake.CategoryChannel,
                                access_roles: list[disnake.Role],
                                deny_roles: list[disnake.Role]):
        guild: disnake.Guild = access_roles[0].guild

        access_roles = set(access_roles)
        access_roles.add(guild.me)

        deny_roles = set(deny_roles)
        deny_roles.add(guild.default_role)

        # get roles needed for permission overwrites
        return {
            "name": cls._get_channel_name(name, progress),
            "topic": "Use /wip to update this WIP",
            "reason": "/wipify",
            "category": category,
            "position": 0,
            "overwrites": {
                **{role: disnake.PermissionOverwrite(view_channel=True)
                   for role in access_roles},
                **{role: disnake.PermissionOverwrite(view_channel=False)
                   for role in deny_roles}
            }
        }

    @classmethod
    async def from_channel(
            cls, *,
            name: str,
            progress: Union[str, int],
            track: Optional[soundcloud.Track] = None,
            existing_channel: Optional[disnake.TextChannel] = None,
            extra_members: Optional[list[disnake.Member]] = None):

        # get guild
        if existing_channel is None and not extra_members:
            raise ValueError("Must specify either a channel or extra members")
        guild = existing_channel.guild if existing_channel \
            else extra_members[0].guild

        # validate inputs
        cls._validate_name(name, guild)
        progress = cls._purify_progress(progress)

        if existing_channel:
            if disnake.utils.get(State().wips, channel=existing_channel):
                raise UserError("This channel is already a WIP.")

        # get WIPs category
        wips_category = disnake.utils.get(guild.categories, name="WIPs")
        if wips_category is None:
            raise UserError("Could not find a channel category called WIPs.")

        # roles that are specifically denied access
        webcage_role = disnake.utils.get(guild.roles, name="webcage")
        if webcage_role is None:
            raise UserError("Couldn't find a role called 'webcage'")

        # roles that are allowed access
        view_wips_role = disnake.utils.get(guild.roles, name="view wips")
        if view_wips_role is None:
            raise UserError("Couldn't find a role called 'view wips'")

        # create new role for allowing access
        new_role = await guild.create_role(
            name=name,
            permissions=disnake.Permissions.none(),
            mentionable=True,
            reason="/wipify")

        members = set(extra_members if extra_members else [])
        # get members
        if existing_channel:
            async for msg in existing_channel.history(limit=1000):
                if msg.attachments and \
                        msg.attachments[0].content_type.startswith("audio"):
                    if msg.author != guild.me:
                        members.add(msg.author)

        # no point doing these in parallel, we get ratelimited anyway
        for member in members:
            await member.add_roles(new_role, reason="/wipify")

        # update the channel
        kwargs = cls._get_new_channel_kwargs(
            name=name,
            progress=progress,
            category=wips_category,
            access_roles=(view_wips_role, new_role),
            deny_roles=(webcage_role,)
        )

        if existing_channel:
            await existing_channel.edit(**kwargs)
            channel = existing_channel
        else:
            channel = await guild.create_text_channel(**kwargs)

        # create the wip
        wip = Wip(name=name,
                  progress=progress,
                  track=track,
                  channel=channel,
                  role=new_role,
                  updates=[],
                  credit={
                      "producers": [],
                      "vocalists": []
                  },
                  messages={
                      "pinned": None,
                      "last_update": None
                  },
                  created_timestamp=disnake.utils.utcnow())

        # send the pinned message
        await wip.update_pinned()

        State().wips.append(wip)
        State().save()
        return wip

    # TODO remove (replace w as_embed)
    def view_embed(self):
        timestamp = self.created_timestamp
        if len(self.updates) > 0:
            timestamp = self.updates[-1].timestamp

        embed = disnake.Embed(
            color=disnake.Color.blue(),
            title=f"{self.name} ({self.progress}%)",
            timestamp=timestamp
        )
        embed.set_footer(
            text="Last update",
            icon_url=WUCK
        )

        vocalists = "nobody"
        producers = "nobody"
        if self.credit.vocalists:
            vocalists = "\n".join(
                map(lambda a: f"<@{a.id}>", self.credit.vocalists))
        if self.credit.producers:
            producers = "\n".join(
                map(lambda a: f"<@{a.id}>", self.credit.producers))

        embed.add_field(name="featuring:", value=vocalists, inline=False)
        embed.add_field(name="produced by:", value=producers, inline=False)

        # TODO
        # - link to most recent update
        # - link to soundcloud
        # (maybe with buttons?)

        return embed

    def soundcloud_description(self):
        vocalists = self.credit.vocalists
        vocalists = (v for v in vocalists if v in State().soundclouds)
        vocalists = ["@" + State().soundclouds[v].permalink for v in vocalists]
        vocalists = vocalists or ["nobody"]

        producers = self.credit.producers
        producers = (p for p in producers if p in State().soundclouds)
        producers = ["@" + State().soundclouds[p].permalink for p in producers]
        producers = producers or ["nobody"]

        return "\n".join(
            ["featuring:", *vocalists, "\nproduced by:", *producers])

    def unlinked_members(self):
        members = set(*self.credit.vocalists, *self.credit.producers)
        linked = set(State().soundclouds.keys())
        return members - linked

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
        if self.updates and use_update_timestamp:
            embed.timestamp = self.updates[-1].timestamp
            embed.set_footer(
                text="last update",
                icon_url=WUCK
            )
        else:
            embed.timestamp = self.created_timestamp
            embed.set_footer(text="created on", icon_url=WUCK)

        # set up credit
        if show_help:
            vocalists = "nobody (try `/wip credit vocalist`)"
            producers = "nobody (try `/wip credit producer`)"
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
        if self.track:
            links.append(f"[soundcloud]({self.track.url})")
        if self.updates:
            links.append(f"[last update]({self.updates[-1].update.jump_url})")

        if links:
            embed.add_field(
                name="links:", value="\n".join(links), inline=False)

        return embed

    async def update_pinned(self):

        embed = self.as_embed(
            title_prefix="\N{PUSHPIN}",
            include_links=True,
            use_update_timestamp=True,
            show_help=True)

        if self.pinned is None:
            self.pinned = await self.channel.send(embed=embed)
        else:
            await self.pinned.edit(embed=embed)

        if not self.pinned.pinned:
            await self.pinned.pin()

    async def edit(self, *,
                   name: Optional[str] = None,
                   progress: Optional[Union[str, int]] = None):

        if name is not None:
            # check for name collision
            if self.name == name:
                raise UserError(f"This WIP is already called `{name}`.")
            self._validate_name(name, self.guild)

        if progress is not None:
            progress = self._purify_progress(progress)

        self.name = name or self.name
        self.progress = progress or self.progress

        if name is not None or progress is not None:
            await self.channel.edit(
                name=self._get_channel_name(self.name, self.progress))

        if self.updates:
            update_embed = self.as_embed(
                title_prefix="\N{BELL}",
                include_links=False,
                use_update_timestamp=False,
                show_help=False)
            await self.updates[-1].update.edit(embed=update_embed)

        if self.track:
            await self.track.edit(
                title=name,
                description=self.soundcloud_description()
            )

        await self.update_pinned()
