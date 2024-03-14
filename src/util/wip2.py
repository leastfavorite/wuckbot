import disnake
from typing import Optional, Union
from datetime import datetime

from util.json import State, JsonSerializable
from util.decorators import UserError
from util.embeds import WUCK


class SoundcloudTrack:
    pass


class Wip(JsonSerializable):
    MANIFEST = {
        "name": str,
        "progress": int,
        "soundcloud": Optional[SoundcloudTrack],
        "channel": disnake.TextChannel,
        "role": disnake.Role,
        "credit": {
            "producers": list[disnake.Member],
            "vocalists": list[disnake.Member]
        },
        "messages": {
            "pinned": Optional[disnake.Message],
            "update": Optional[disnake.Message]
        },
        "work_timestamp": datetime
    }

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
    async def from_channel(
            cls, *,
            name: str,
            progress: Union[str, int],
            soundcloud: Optional[SoundcloudTrack] = None,
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

        # TODO: ideally these could be found at init?
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
        wip = Wip(None,
                  name=name,
                  progress=progress,
                  soundcloud=soundcloud,
                  channel=channel,
                  role=new_role,
                  messages={
                      "pinned": None,
                      "update": None
                  },
                  work_timestamp=disnake.utils.utcnow())

        # send the pinned message
        pinned = await channel.send(embed=wip.get_pinned_embed())
        await pinned.pin()
        wip.messages.pinned = pinned

        State().wips.append(wip)
        return wip

    async def update_pinned(self):
        embed = disnake.Embed(
            color=disnake.Color.blue(),
            title=f"\N{PUSHPIN} {self.name} ({self.progress}%)",
            timestamp=self.work_timestamp
        )
        embed.set_footer(
            text="Last update",
            icon_url=WUCK
        )

        vocalists = "nobody (try `/wip credit vocalist`)"
        producers = "nobody (try `/wip credit producer`)"
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
        if self.messages.pinned is not None:
            self.messages.pinned = await self.channel.send(embed=embed)
            await self.messages.pinned.pin()
        else:
            await self.messages.pinned.edit(embed=embed)

    async def edit(self, *,
                   name: Optional[str] = None,
                   progress: Optional[Union[str, int]] = None,
                   update: Optional[disnake.Message] = None,
                   work_timestamp: Optional[datetime] = None):

        if name is not None:
            # check for name collision
            if self.name == name:
                raise UserError(f"This WIP is already called `{name}`.")
            self._validate_name(name, self.guild)

        if progress is not None:
            progress = self._purify_progress(progress)

        self.name = name
        self.progress = progress
        self.update = update
        self.work_timestamp = work_timestamp

        if name is not None or progress is not None:
            await self._channel.edit(
                name=self._get_channel_name(self.name, self.progress))

        await self.update_pinned()
