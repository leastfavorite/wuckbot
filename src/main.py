import disnake
from disnake.ext import commands

import json
import importlib
import asyncio

from inspect import isclass, signature

from datatypes import Secrets, State
import soundcloud

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
    test_guilds = secrets["test_guilds"]
    oauth_token = secrets["soundcloud_oauth"]
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
        cogs = []
        state_manifest = {}
        secrets_manifest = {
            "test_guilds": list[int],
            "bot_token": str,
            "admin": disnake.User,
            "soundcloud_oauth": str
        }
        # import cogs first to load manifest
        for ext in disnake.utils.search_directory(COGS_FOLDER):
            ext_module = importlib.import_module(ext.removeprefix("src."))
            cogs.extend(c for c in ext_module.__dict__.values() if
                        isclass(c) and issubclass(c, commands.Cog))
            state_manifest.update(
                getattr(ext_module, "STATE_MANIFEST", {}))
            secrets_manifest.update(
                getattr(ext_module, "SECRETS_MANIFEST", {}))

        # load json
        await State.create(
            STATE_FILENAME, state_manifest, bot=bot, sc=sc)
        await Secrets.create(
            SECRETS_FILENAME, secrets_manifest, bot=bot, sc=sc)

        # load cogs
        for cog in cogs:
            print(f"Initializing {cog.__qualname__}...")
            params = signature(cog.__init__).parameters.keys()
            all_kwargs = {"bot": bot, "sc": sc}
            kwargs = {k: v for (k, v) in all_kwargs.items() if k in params}
            bot.add_cog(cog(**kwargs))

        # we don't want to run this multiple times
        bot.remove_listener(_on_ready, "on_ready")

    bot.add_listener(_on_ready, "on_ready")

    try:
        loop.run_until_complete(bot.start(token=bot_token))
    except KeyboardInterrupt:
        State().save()
        Secrets().save()
        loop.run_until_complete(bot.close())
        loop.run_until_complete(sc.close())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
