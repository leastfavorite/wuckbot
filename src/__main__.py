import disnake
from disnake.ext import commands

import json
import asyncio

from inspect import signature

from .datatypes import Secrets, State
from . import validator, soundcloud, cogs

SECRETS_FILENAME = "secrets.json"
STATE_FILENAME = "state.json"
COGS_FOLDER = "src/cogs"

def main():
    loop = asyncio.new_event_loop()

    # we have to hack some initialization stuff out of the secrets file
    # because we can't get it as a fancy object until the bot is started
    with open(SECRETS_FILENAME, "r") as fp:
        secrets = json.load(fp)
    bot_token = secrets["bot_token"]
    test_guilds = secrets["guilds"]
    oauth_token = secrets["sc_oauth"]
    del secrets

    intents = disnake.Intents.default()
    intents.members = True
    intents.message_content = True
    bot = commands.InteractionBot(
        intents=intents,
        test_guilds=test_guilds,
        loop=loop)

    sc = loop.run_until_complete(soundcloud.Client.create(oauth_token))

    async def _on_ready():

        registrar = validator.Registrar(
            *validator.base_serializers(),
            *validator.disnake_serializers(bot),
            *soundcloud.serializers(sc)
        )

        # load json
        await State.load("state.json", "backups/state", registrar)
        await Secrets.load("secrets.json", "backups/secrets", registrar)

        for cog_name in cogs.__all__:
            Cog = getattr(cogs, cog_name)
            print(f"Initializing {cog_name}...")

            all_kwargs = {"bot": bot, "sc": sc}

            params = signature(Cog.__init__).parameters.keys()
            kwargs = {k: v for (k, v) in all_kwargs.items() if k in params}

            bot.add_cog(Cog(**kwargs))

        # we don't want to run this multiple times
        bot.remove_listener(_on_ready, "on_ready")

    bot.add_listener(_on_ready, "on_ready")

    try:
        loop.run_until_complete(bot.start(token=bot_token))
    except KeyboardInterrupt:
        loop.run_until_complete(State().save())
        loop.run_until_complete(Secrets().save())
        loop.run_until_complete(bot.close())
        loop.run_until_complete(sc.close())
    finally:
        loop.close()

if __name__ == "__main__":
    main()
