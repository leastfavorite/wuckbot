from disnake.ext import commands, tasks
import disnake

import aiohttp

from .. import soundcloud
from ..utils import send_error, UserError, embeds, buttons, error_handler, send_modal

class OauthCog(commands.Cog):
    def __init__(self, bot: commands.InteractionBot, sc: soundcloud.Client):
        self.bot = bot
        self.sc = sc
        self.messages: list[disnake.Message] = []
        self.check_oauth.start()

        self.sc.register_oauth_expire_callback(self.on_oauth_expire)

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
            "**In Chrome or Chrome-like browsers:**",
            "- Select `Application` in the new window that opens.",
            "- Under the `Storage` header on the left side, click `Cookies`.",
            "**In Firefox:**",
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
            self.sc.oauth_token = token
            # token found!! it's already applied, just delete all
            # calls to action and return
            try:
                for msg in reversed(self.messages):
                    await msg.delete()
                    self.messages.remove(msg)
            except (disnake.Forbidden, disnake.NotFound):
                pass

            await inter.followup.send(
                ephemeral=True,
                embed=embeds.success(
                    "Thank you! Please don't share the token with anybody.")
            )
            return

        await inter.followup.send(
            ephemeral=True,
            embed=embeds.error(
                "That token doesn't work. Please try again.")
        )

    # TODO: honestly this should should be in soundcloud.Client
    async def test_token(self, token: str | None = None):
        try:
            await self.sc.routes["me"].run(retry=True, oauth_token=token)
        except aiohttp.ClientResponseError as e:
            if e.status == 401:
                return False
            raise e
        return True

    async def on_oauth_expire(self):
        # send to every guild
        for guild in self.bot.guilds:
            self.messages.append(
                await send_error(
                    guild=guild,
                    embed=embeds.error(
                        title="SoundCloud OAuth Token Expired",
                        msg="If you're an administrator, please click the "
                            "button below to provide a new token."),
                    components=[buttons.oauth_instructions()]
            ))

    @tasks.loop(hours=3.0)
    async def check_oauth(self):
        await self.test_token()

    @check_oauth.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()
