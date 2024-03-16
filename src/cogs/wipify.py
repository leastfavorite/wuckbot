import disnake
from disnake.ext import commands

from util.modal import send_modal
from util.decorators import error_handler, UserError
from util import embeds

from secrets import token_hex

from util.wip import Wip
from util.json import State


STATE_MANIFEST = {
    "wips": list[Wip]
}

class WipifyCog(commands.Cog):
    def __init__(self,
                 bot: commands.InteractionBot):
        self.bot = bot

    # delete all bot pin messages
    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        if message.type != disnake.MessageType.pins_add:
            return
        if message.author.id != message.guild.me.id:
            return
        if message.channel.category.name == "WIPs":
            await message.delete()

    @commands.Cog.listener("on_button_click")
    @error_handler
    async def on_button_click(self, inter: disnake.MessageInteraction):
        if inter.component.custom_id.startswith("wip_join_"):
            channel_id = int(
                inter.component.custom_id.removeprefix("wip_join_"))
            wip = disnake.utils.get(State().wips, channel__id=channel_id)
            if not wip:
                raise UserError("This WIP no longer exists.")
            role: disnake.Role = wip.role
            if role in inter.author.roles:
                raise UserError("You're already in this WIP!")
            await inter.author.add_roles(role)
            await inter.response.send_message(
                embed=embeds.success(
                    f"You have been added to {wip.channel.mention}.\n"
                    f"To leave, use `/wip leave` from within its channel.")
            )


    # sends the wip modal and validates all input text
    async def _send_wip_modal(self,
                              inter: disnake.ApplicationCommandInteraction,
                              modal_title: str,
                              modal_song_placeholder: str,
                              modal_offer_soundcloud: bool = False,
                              ephemeral: bool = False):
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
        modal = await send_modal(inter, **modal, ephemeral=ephemeral)

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

        filename = message.attachments[0].filename
        modal = await self._send_wip_modal(
            inter,
            modal_title=f"Create WIP with {message.author.global_name}",
            modal_song_placeholder=filename,
            modal_offer_soundcloud=False,
            ephemeral=False
        )

        wip = await Wip.from_channel(name=modal.name,
                                     progress=modal.progress,
                                     soundcloud=modal.soundcloud,
                                     existing_channel=None,
                                     extra_members=tuple({
                                         inter.author, message.author}))

        embed = disnake.Embed(
            color=disnake.Color.blue(),
            title=f"New WIP: {wip.name}"
        )
        embed.add_field(
            name="Original File",
            value=message.jump_url,
            inline=False)
        embed.add_field(
            name="WIP Author",
            value=inter.author.mention,
            inline=True)
        embed.add_field(
            name="File Author",
            value=message.author.mention,
            inline=True)

        embed.set_footer(text=embeds.success().footer.text,
                         icon_url=embeds.WUCK)

        await inter.followup.send(
            embed=embed,
            components=[disnake.ui.Button(
                label="Join WIP",
                style=disnake.ButtonStyle.primary,
                custom_id=f"wip_join_{wip.channel.id}")])
