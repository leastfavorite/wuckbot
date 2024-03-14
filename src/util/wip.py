import disnake
from datetime import datetime, timezone
from typing import Optional, Union

from util.embeds import WUCK
from util.decorators import UserError
from util.json import JsonSerializable


# TODO
class SoundcloudTrack:
    pass


class Wip:
    pass


# usage:
#   credit.producers += member
#   credit.producers -= member
#   credit.vocalists ^= member
class WipCreditedMembers:
    def __init__(self, members=list[disnake.Member]):
        self._members = members
        self._parent = None

    def __contains__(self, other: disnake.Member):
        return disnake.utils.get(self._members, id=other.id) is not None

    @property
    def members(self):
        return tuple(self._members)

    def __iter__(self):
        return iter(tuple(self._members))

    async def remove(self, other: disnake.Member):
        if other not in self._members:
            return
        self._members.remove(other)
        if self._parent:
            await self._parent._update_credit()

    async def add(self, other: disnake.Member):
        if other in self._members:
            return
        self._members.append(other)
        if self._parent:
            await self._parent._update_credit()

    def __bool__(self):
        return len(self._members) > 0


class WipCredit:

    def __init__(self, *,
                 producers: list[disnake.Member],
                 vocalists: list[disnake.Member]):
        self._producers = WipCreditedMembers(producers)
        self._vocalists = WipCreditedMembers(vocalists)

    def _assign_parent(self, parent: Wip):
        self._producers._parent = parent
        self._vocalists._parent = parent

    @property
    def producers(self):
        return self._producers

    @property
    def vocalists(self):
        return self._vocalists

    @classmethod
    def from_state(cls, guild, state):
        producers = []
        for producer in state.producers:
            producers.append(guild.get_member(producer))

        vocalists = []
        for vocalist in state.vocalists:
            vocalists.append(guild.get_member(vocalist))

        return cls(
            producers=producers,
            vocalists=vocalists)

    def to_state(self):
        return {
            "producers": list(map(lambda user: user.id, self.producers)),
            "vocalists": list(map(lambda user: user.id, self.vocalists))
        }


class Wip(JsonSerializable):
    def __init__(self, *,
                 name: str,
                 progress: int,
                 credit: Optional[WipCredit] = None,
                 soundcloud: Optional[SoundcloudTrack] = None,
                 channel: disnake.TextChannel,
                 pinned: disnake.Message,
                 role: disnake.Role,
                 update: Optional[disnake.Message] = None,
                 work_timestamp: datetime):
        self._name = name
        self._progress = progress

        self._soundcloud = soundcloud
        self._channel = channel
        self._pinned = pinned
        self._role = role
        self._update = update
        self._work_timestamp = work_timestamp

        if credit:
            self._credit = credit
        else:
            self._credit = WipCredit(producers=[], vocalists=[])
        self._credit._assign_parent(self)

    @classmethod
    async def from_state(cls, client: disnake.Client, base_state, state):

        # TODO handle error cases
        guild = client.get_guild(state.discord.guild)

        # get credits
        credit = WipCredit.from_state(guild, state.credit)
        channel = guild.get_channel(state.discord.channel)
        pinned = await channel.fetch_message(state.discord.pinned)
        role = guild.get_role(state.discord.role)

        if "update" in state.discord:
            update_channel = guild.get_channel(state.discord.update.channel)
            update = update_channel.get_message(state.discord.update.message)
        else:
            update = None

        work_timestamp = datetime.fromtimestamp(state.work_timestamp,
                                                timezone.utc)
        return cls(
            base_state,
            state,
            name=state.name,
            progress=state.progress,
            credit=credit,
            channel=channel,
            pinned=pinned,
            role=role,
            update=update,
            work_timestamp=work_timestamp
        )

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
        bars = [x for list_ in bars for x in list_]
        bars.append("\U00002B50\U0001F389\U0001F973")

        bar = bars[(len(bars)-1)*progress//100]

        return f"{bar}-{name.lower().replace(' ', '-')}"

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
            cls, base_state, *,
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
        cls._validate_name(name, base_state, guild)
        progress = cls._purify_progress(progress)

        if existing_channel:
            if disnake.utils.get(
                    base_state.wips, discord__channel=existing_channel.id):
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
        wip = Wip(base_state, None,
                  name=name,
                  progress=progress,
                  soundcloud=soundcloud,
                  channel=channel,
                  pinned=None,
                  role=new_role,
                  update=None,
                  work_timestamp=disnake.utils.utcnow())

        # send the pinned message
        pinned = await channel.send(embed=wip.get_pinned_embed())
        await pinned.pin()
        wip._pinned = pinned

        base_state.wips.append(wip.get_state())
        wip._state = base_state.wips[-1]

        return wip

    @property
    def name(self) -> str:
        return self._name

    @property
    def progress(self) -> int:
        return self._progress

    @property
    def credit(self) -> WipCredit:
        return self._credit

    @property
    def soundcloud(self) -> Optional[SoundcloudTrack]:
        return self._soundcloud

    @property
    def channel(self) -> disnake.TextChannel:
        return self._channel

    @property
    def pinned(self) -> disnake.Message:
        return self._pinned

    @property
    def role(self) -> disnake.Role:
        return self._role

    @property
    def update(self) -> Optional[disnake.Message]:
        return self._update

    @property
    def work_timestamp(self) -> datetime:
        return self._work_timestamp

    @property
    def guild(self) -> disnake.Guild:
        return self._channel.guild

    @staticmethod
    def _validate_name(name: str, base_state, guild: disnake.Guild):
        if disnake.utils.get(base_state.wips, name=name) is not None:
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

    async def edit(self, *,
                   name: Optional[str] = None,
                   progress: Optional[Union[str, int]] = None,
                   update: Optional[disnake.Message] = None,
                   work_timestamp: Optional[datetime] = None):

        if name is not None:
            # check for name collision
            if self.name == name:
                raise UserError(f"This WIP is already called `{name}`.")
            self._validate_name(name, self._base_state, self.guild)

        if progress is not None:
            progress = self._purify_progress(progress)

        if name is not None:
            self._name = name
        if progress is not None:
            self._progress = progress
        if update is not None:
            self._update = update
        if work_timestamp is not None:
            self._work_timestamp = work_timestamp

        if name is not None or progress is not None:
            name = name if name is not None else self.name
            progress = progress if progress is not None else self.progress
            await self._channel.edit(
                name=self._get_channel_name(name, progress))

        self._update_state()
        await self.pinned.edit(embed=self.get_pinned_embed())

    def get_state(self):
        ret = {
            "name": self._name,
            "progress": self._progress,
            "credit": self._credit.to_state(),
            "discord": {
                "guild": self._channel.guild.id,
                "channel": self._channel.id,
                "pinned": self._pinned.id,
                "role": self._role.id
            },
            "work_timestamp": self._work_timestamp.timestamp()
        }

        if self._update is not None:
            ret["discord"]["update"] = {
                "channel": self._update.channel.id,
                "message": self._update.id
            }

        if self._soundcloud is not None:
            ret["soundcloud"] = self._soundcloud.to_state()

        return ret

    def _update_state(self):
        new_state = self.get_state()
        for k, v in new_state.items():
            if self._state.get(k) != v:
                self._state[k] = v

    async def _update_credit(self):
        self._update_state()
        await self.pinned.edit(embed=self.get_pinned_embed())

    def get_pinned_embed(self):
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
        return embed
