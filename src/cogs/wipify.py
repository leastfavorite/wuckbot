import disnake
from disnake.ext import commands

from util.modal import send_modal
from util.decorators import error_handler, UserError
from util import embeds

from secrets import token_hex

from util.wip import Wip


class WipifyCog(commands.Cog):
    def __init__(self,
                 bot: commands.InteractionBot,
                 state):
        self.bot = bot
        self.state = state
        if "wips" not in self.state:
            self.state.wips = []

    # sends the wip modal and validates all input text
    async def _send_wip_modal(self,
                              inter: disnake.ApplicationCommandInteraction,
                              modal_title: str,
                              modal_song_placeholder: str,
                              modal_offer_soundcloud: bool = False):
        modal = {
            "title": modal_title,
            "custom_id": token_hex(16),
            "components": [
                disnake.ui.TextInput(
                    label="working title",
                    placeholder=modal_song_placeholder,
                    custom_id="name",
                    max_length=50
                ),
                disnake.ui.TextInput(
                    label="current progress (as a percentage)",
                    placeholder="10%",
                    custom_id="progress",
                    max_length=4
                )
            ]
        }

        if modal_offer_soundcloud:
            modal["components"].append(disnake.ui.TextInput(
                label="soundcloud link",
                placeholder="(leave empty if nothing is uploaded)",
                custom_id="soundcloud",
                required=False
            ))
        modal = await send_modal(inter, **modal)

        if not hasattr(modal, "soundcloud"):
            modal.soundcloud = None
        if modal.soundcloud == "":
            modal.soundcloud = None

        return modal

    @commands.slash_command(
        description="Mark a channel as a WIP",
        dm_permission=False,
        default_member_permissions=disnake.Permissions.none())
    @error_handler
    async def wipify(self, inter: disnake.ApplicationCommandInteraction):
        # create modal
        modal = await self._send_wip_modal(
            inter,
            modal_title=f"Register #{inter.channel.name} as a WIP",
            modal_song_placeholder=inter.channel.name,
            modal_offer_soundcloud=not inter.channel.name.startswith("sketch")
        )

        # create WIP
        await Wip.from_channel(
            self.state,
            name=modal.name,
            progress=modal.progress,
            soundcloud=modal.soundcloud,
            existing_channel=inter.channel,
            extra_members=(inter.author,)
        )

        await inter.followup.send(embed=embeds.success(
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

        await Wip.from_channel(self.state,
                               name=modal.title,
                               progress=modal.progress,
                               soundcloud=modal.soundcloud,
                               existing_channel=None,
                               extra_members={inter.author, message.author})

        await inter.response.send_message(embed=embeds.success(
            "Channel created successfully."))
