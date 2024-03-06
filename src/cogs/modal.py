import disnake
from disnake.ext import commands
import asyncio

from util.decorators import error_handler

from util.modal import send_modal

class ModalCog(commands.Cog):
    def __init__(self, bot: commands.InteractionBot, state):
        self.bot = bot
        self.state = state

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
