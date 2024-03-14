import disnake
from disnake.ext import commands
from util.decorators import error_handler
from util.modal import send_modal


class ModalCog(commands.Cog):
    def __init__(self, bot: commands.InteractionBot):
        self.bot = bot

    @commands.slash_command(description="Balls")
    @error_handler
    async def test(self, inter: disnake.ApplicationCommandInteraction):
        await send_modal(inter,
            title="test",
            custom_id="test",
            components=[
                disnake.ui.TextInput(
                    label="test",
                    custom_id="test1"
                )
            ]
        )

        raise ValueError("hi")


def setup(bot):
    bot.add_cog(ModalCog(bot))
