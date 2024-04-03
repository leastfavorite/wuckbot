from disnake.ext import commands, tasks
import disnake

from ..utils import error_handler, buttons, get_audio_attachment, embeds
from ..filemethods import state

class SketchCog(commands.Cog):
    def __init__(self, bot: commands.InteractionBot):
        self.bot = bot

    @commands.slash_command(
        dm_permission=False,
        default_member_permissions=disnake.Permissions.none())
    @error_handler()
    async def sendsketchembed(self,
                              inter: disnake.ApplicationCommandInteraction):
        """
        Sends an embed with a "Create Sketch" button.
        """
        embed = disnake.Embed(
            color=disnake.Color.blurple(),
            title="\N{ELECTRIC LIGHT BULB} Create a Sketch \N{ELECTRIC LIGHT BULB}",
            description="Sketches are public channels for fleshing out new ideas, "
                        "often in vc. You can think of them as the precursor to a "
                        "WIP channel.\n"
                        "They can be turned into WIPs with `/wipify`, "
                        "and are archived if inactive for three days."
        )

        await inter.channel.send(
            embed=embed,
            components=[buttons.new_sketch()])

        await inter.response.send_message(
            ephemeral=True,
            embed=embeds.success("Embed sent!"))

    @commands.Cog.listener("on_message")
    async def on_message(self, message: disnake.Message):
        sketch = disnake.utils.get(state().sketches, channel=message.channel)
        if sketch and get_audio_attachment(message):
            sketch.timestamp = disnake.utils.utcnow()
