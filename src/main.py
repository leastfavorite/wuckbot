import disnake
from disnake.ext import commands

import json
import importlib
from inspect import isclass
from util.json import Secrets, State

SECRETS_FILENAME = "secrets.json"
STATE_FILENAME = "state.json"
COGS_FOLDER = "src/cogs"


def main():

    # we have to hack some initialization stuff out of the secrets file
    # because we can't get it as a fancy object until the bot is started
    with open(SECRETS_FILENAME, "r") as fp:
        secrets = json.load(fp)
    bot_token = secrets["bot_token"]
    test_guilds = secrets["test_guilds"]
    del secrets

    # setup bot
    intents = disnake.Intents.default()
    intents.members = True
    intents.message_content = True
    bot = commands.InteractionBot(
        intents=intents, test_guilds=test_guilds)

    # wait for ready to do async stuff--that way we still get to use
    # bot.run
    async def _on_ready():
        cogs = []
        # import cogs (executing these once lets all classes get registered)
        for ext in disnake.utils.search_directory(COGS_FOLDER):
            ext_module = importlib.import_module(ext.removeprefix("src."))
            cogs.extend(c for c in ext_module.__dict__.values() if
                        isclass(c) and issubclass(c, commands.Cog))

        # load json
        await State.from_file(bot, STATE_FILENAME)
        await Secrets.from_file(bot, SECRETS_FILENAME)

        # load cogs
        for cog in cogs:
            print(f"Initializing {cog.__qualname__}...")
            bot.add_cog(cog(bot))

        # TODO: add reload cmd
        # @commands.slash_command(
        #     dm_permission=True,
        #     default_member_permissions=disnake.Permissions.all())
        # async def reload(inter: disnake.ApplicationCommandInteraction):
        #     await bot.reload_extension

    bot.add_listener(_on_ready, "on_ready")

    bot.run(token=bot_token)


if __name__ == "__main__":
    main()
