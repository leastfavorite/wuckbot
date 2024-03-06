import disnake
from disnake.ext import commands

from util.modal import send_modal
from util.decorators import error_handler, UserError
from util import embeds

from typing import Optional
from secrets import token_hex


def get_wip_channel_name(name, progress):
    r = "\U0001F7E5"
    y = "\U0001F7E8"
    g = "\U0001F7E9"
    b = "\U00002B1B"
    done = "\u2B50\U0001F389\U0001F973"

    bars = [
        b+b+b, r+b+b, r+r+b, r+r+r, y+r+r, y+y+r,
        y+y+y, g+y+y, g+g+y, g+g+g, done
    ]
    return f"{bars[progress//10]}-{name.lower().replace(' ', '-')}"


class WipifyCog(commands.Cog):
    def __init__(self,
                 bot: commands.InteractionBot,
                 state):
        self.bot = bot
        self.state = state
        if "wips" not in self.state:
            self.state.wips = []

    # gets the modal used for /wipify
    def _get_modal(self, title, song_title_placeholder, link_soundcloud=True):
        ret = {
            "title": title,
            "custom_id": token_hex(16),
            "components": [
                disnake.ui.TextInput(
                    label="working title",
                    placeholder=song_title_placeholder,
                    custom_id="name",
                    style=disnake.TextInputStyle.short,
                    min_length=1,
                    max_length=50
                ),
                disnake.ui.TextInput(
                    label="current progress (as a percentage)",
                    placeholder="10%",
                    custom_id="progress",
                    style=disnake.TextInputStyle.short,
                    min_length=1,
                    max_length=4
                )
            ]
        }

        if link_soundcloud:
            ret["components"].append(disnake.ui.TextInput(
                label="soundcloud link",
                placeholder="(leave empty if nothing is uploaded)",
                custom_id="soundcloud",
                required=False,
                style=disnake.TextInputStyle.single_line
            ))

        return ret

    # sends the wip modal and validates all input text
    async def _send_wip_modal(self,
                              inter: disnake.ApplicationCommandInteraction,
                              modal):
        modal = await send_modal(inter, **modal)

        # verify name is unused internally
        if disnake.utils.get(self.state.wips, name=modal.name) is not None:
            raise UserError(f"The name \"{modal.name}\" is already in use.")

        # verify name is not an existing role
        if disnake.utils.get(inter.guild.roles, name=modal.name) is not None:
            raise UserError(
                f"The name \"{modal.name}\" is already a role in this server.")

        # verify soundcloud link is unused
        if not hasattr(modal, "soundcloud"):
            modal.soundcloud = None

        if modal.soundcloud is not None:
            sc_conflict = disnake.utils.get(
                self.state.wips, soundcloud=modal.soundcloud)
            if sc_conflict is not None:
                raise UserError(
                    f"That SoundCloud link is already used by "
                    f"{sc_conflict.name}.")

        # verify progress is a percentage
        if type(modal.progress) is str:
            progress = modal.progress
            try:
                modal.progress = int(progress.rstrip("%"), 10)
            except ValueError:
                raise UserError(
                    f"Could not parse \"{progress}\" as a percentage.")

        if modal.progress < 0 or modal.progress > 100:
            raise UserError(
                f"Could not parse \"{progress}\" as a percentage.")

        return modal

    async def _create_wip_channel(self,
                                  name: str,
                                  members: list[disnake.Member],
                                  progress: int,
                                  soundcloud: Optional[str] = None,
                                  *,
                                  message: disnake.Message = None,
                                  channel: disnake.TextChannel = None):

        # validate inputs
        if message is None and channel is None:
            raise ValueError("must provide one of message or channel")
        if message is not None and channel is not None:
            raise ValueError("must provide only one of message or channel")

        if message:
            guild: disnake.Guild = message.guild
        if channel:
            guild: disnake.Guild = channel.guild

        # get roles needed for permission overwrites
        webcage_role = disnake.utils.get(guild.roles, name="webcage")
        if webcage_role is None:
            raise UserError("Couldn't find a role called 'webcage'")
        view_wips_role = disnake.utils.get(guild.roles, name="view wips")
        if view_wips_role is None:
            raise UserError("Couldn't find a role called 'view wips'")

        # get WIPs category
        wips_category = disnake.utils.get(guild.categories, name="WIPs")
        if wips_category is None:
            raise UserError("Could not find a channel category called WIPs.")

        wip_role = await guild.create_role(
            name=name,
            permissions=disnake.Permissions.none(),
            mentionable=True,
            reason="/wipify"
        )

        for member in members:
            await member.add_roles(wip_role)

        kwargs = {
            "name": get_wip_channel_name(name, progress),
            "topic": "Use /wip to update this WIP",
            "reason": "/wipify",
            "category": wips_category,
            "position": 0,
            "overwrites": {
                guild.me: disnake.PermissionOverwrite(view_channel=True),
                wip_role: disnake.PermissionOverwrite(view_channel=True),
                view_wips_role: disnake.PermissionOverwrite(view_channel=True),
                webcage_role: disnake.PermissionOverwrite(view_channel=False),
                guild.default_role:
                    disnake.PermissionOverwrite(view_channel=False)
            }
        }
        if channel is None:
            channel = await guild.create_text_channel(**kwargs)
        else:
            await channel.edit(**kwargs)

        self.state.wips.append({
            "name": name,
            "channel": channel.id,
            "role": wip_role.id,
            "progress": progress,
            "soundcloud": soundcloud,
            "credit": {
                "vocalist": [],
                "producer": []
            }
        })

        return channel, wip_role

    @commands.slash_command(
        description="Mark a channel as a WIP",
        dm_permission=False,
        default_member_permissions=disnake.Permissions.none())
    @error_handler
    async def wipify(self, inter: disnake.ApplicationCommandInteraction):
        # ensure channel is not already a WIP
        if disnake.utils.get(self.state.wips, channel=inter.channel_id):
            raise UserError("This channel is already a WIP!")

        # create modal
        modal = await self._send_wip_modal(inter, self._get_modal(
            title=f"Register #{inter.channel.name} as a WIP",
            song_title_placeholder=inter.channel.name,
            link_soundcloud=not inter.channel.name.startswith("sketch")
        ))

        # get all users
        members = {inter.author}
        async for message in inter.channel.history(limit=1000):
            if message.attachments and \
                    message.attachments[0].content_type.startswith("audio"):
                members.add(message.author)

        wip_channel, wip_role = await self._create_wip_channel(
            name=modal.name,
            members=members,
            progress=modal.progress,
            soundcloud=modal.soundcloud,
            channel=inter.channel
        )

        await inter.response.send_message(embed=embeds.success(
            "Channel created successfully."))

    @commands.message_command(
        name="WIPify",
        description="Mark a channel as a WIP",
        dm_permission=False,
        default_member_permissions=disnake.Permissions.none())
    @error_handler
    async def message_wipify(self,
                             inter: disnake.ApplicationCommandInteraction,
                             message: disnake.Message):
        if disnake.utils.get(
                self.state.wips, channel=message.channel.id) is not None:
            raise UserError("You're already in a WIP channel.")

        # create modal
        if not message.attachments or \
                not message.attachments[0].content_type.startswith("audio"):
            sketchpad = disnake.utils.get(message.guild.text_channels,
                                          name="sketchpad")
            if sketchpad is not None:
                raise UserError(
                    "Use this command on a message with an audio file.\n"
                    f"If you're starting a song, use {sketchpad.mention}.")
            else:
                raise UserError(
                    "Use this command on a message with an audio file.")

        modal = await self._send_wip_modal(inter, self._get_modal(
            title=f"Create WIP with {message.author.global_name}",
            song_title_placeholder=message.attachments[0].filename,
            link_soundcloud=False
        ))

        members = {inter.author, message.author}

        wip_channel, wip_role = await self._create_wip_channel(
            name=modal.name,
            members=members,
            progress=modal.progress,
            soundcloud=modal.soundcloud,
            channel=inter.channel
        )

        await inter.response.send_message(embed=embeds.success(
            "Channel created successfully."))
