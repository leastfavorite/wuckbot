from disnake.ext import commands, tasks
import disnake

import aiohttp

from .. import soundcloud
from ..utils import send_error, UserError, embeds, buttons, error_handler, send_modal

class OauthCog(commands.Cog):
    def __init__(self, bot: commands.InteractionBot, sc: soundcloud.Client):
        self.bot = bot
        self.sc = sc
        self.messages: list[disnake.Message] = None
        # self.check_oauth.start()

    @commands.Cog.listener("on_button_click")
    @error_handler()
    async def on_button_click(self, inter: disnake.MessageInteraction):
        if inter.component.custom_id == "oauthinstruction":
            await self.handle_instruction(inter)
        elif inter.component.custom_id == "oauthprovide":
            await self.handle_provide(inter)

    async def handle_instruction(self, inter: disnake.MessageInteraction):
        if not inter.author.guild_permissions.manage_guild:
            raise UserError(
                "You need the `Manage Guild` permission to do this.")

        embed = embeds.success("\n".join([
            "In a private browser window, log into the webcage SoundCloud.",
            "Right-click anywhere on the page and click 'Inspect'.",
            "",
            "In Chrome or Chrome-like browsers:",
            "- Select `Application` in the new window that opens.",
            "- Under the `Storage` header on the left side, click `Cookies`.",
            "In Firefox:",
            "- Select the `Storage` tab.",
            "- Open the `Cookies` header.",
            "",
            "- Open the tab titled `https://soundcloud.com/`.",
            "- In the search bar that says `Filter`, type `oauth_token`.",
            "- The token is under the 'Value' header.",
            "    - It should look like `X-XXXXXX-XXXXXXXXXX-XXXXXXXXXXXXX`.",
            "- Copy the token. Once it's copied, press the button below."
        ]))
        embed.color = disnake.Color.blurple()
        embed.title = "\N{GEAR} Generating a SoundCloud Token \N{GEAR}"

        await inter.response.send_message(
            ephemeral=True,
            embed=embed,
            components=[buttons.oauth_modal()])

    async def handle_provide(self, inter: disnake.MessageInteraction):
        original_message = inter.message

        modal = await send_modal(
            inter,
            title="Enter Token",
            components=[
                disnake.ui.TextInput(
                    label="Token",
                    custom_id="token",
                    placeholder="X-XXXXXX-XXXXXXXXXX-XXXXXXXXXXXXX",
                )
            ],
            ephemeral=True)
        await inter.response.defer(with_message=False, ephemeral=True)

        token: str = modal.token.strip()

        if await self.test_token(token):
            # token found!! it's already applied, just delete all
            # calls to action and return
            try:
                await original_message.delete()
                for msg in self.messages:
                    await msg.delete()
                    del self.messages[msg]
            except (disnake.Forbidden, disnake.NotFound):
                pass

            await inter.followup.send(
                ephemeral=True,
                embed=embeds.success(
                    "Token works! Please don't share it with anybody.")
            )
            return

        await inter.followup.send(
            ephemeral=True,
            embed=embeds.error(
                "That token doesn't work. Please try again.")
        )

    async def test_token(self, token: str = None):
        if token:
            old_token = self.sc.oauth_token
            self.sc.oauth_token = token

        try:
            await self.sc.routes["me"].run(retry=True)
        except aiohttp.ClientResponseError as e:
            if token:
                self.sc.oauth_token = old_token
            if e.status == 401:
                return False
            raise e

        return True

    @commands.Cog.listener("on_message")
    async def on_message(self, message):
        self.sc.oauth_token = "ballspenis"
        try:
            await self.sc.routes["me"].run(retry=True)
        except aiohttp.ClientResponseError as e:
            if e.status != 401:
                raise e

    @tasks.loop(hours=3.0)
    async def check_oauth(self):
        if not await self.test_token():
            # send to every guild
            for guild in self.bot.guilds:
                self.messages.append(
                    await send_error(
                        embed=embeds.error(
                            title="SoundCloud OAuth Token Expired",
                            msg="If you're an administrator, please click the "
                                "button below to provide a new token."),
                        components=[buttons.oauth_instructions()]
                ))


    @commands.slash_command(
        dm_permission=False,
        default_member_permissions=disnake.Permissions.none())
    @error_handler()
    async def invalidate_token(self, inter: disnake.ApplicationCommandInteraction):
        self.sc.oauth_token = "notatoken"
        await inter.response.send_message(
            ephemeral=True,
            embed=embeds.success("Invalidated!")
        )
