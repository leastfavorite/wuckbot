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
    on_close = []

    async def _on_ready():
        sc = await soundcloud.Client.create(oauth_token)
        on_close.append(sc.close())

        registrar = validator.Registrar(
            *validator.base_serializers(),
            *validator.disnake_serializers(bot),
            *soundcloud.serializers(sc)
        )

        # load json
        await State.load("state.json", "backups/state", registrar)
        on_close.append(State().save())

        await Secrets.load("secrets.json", "backups/secrets", registrar)
        on_close.append(Secrets().save())

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

    async def runner() -> None:
        try:
            await bot.start(token=bot_token)
        finally:
            if not bot.is_closed():
                await bot.close()
            await asyncio.gather(*on_close)

    def _shutdown_loop():
        try:
            tasks = {t for t in asyncio.all_tasks(loop=loop) if not t.done()}
            if not tasks:
                return

            for task in tasks:
                task.cancel()

            loop.run_until_complete(
                asyncio.gather(*tasks, return_exceptions=True))

            for task in tasks:
                if task.cancelled():
                    continue
                if task.exception() is not None:
                    loop.call_exception_handler(
                        {
                            "message": "Unhandled exception during shutdown.",
                            "exception": task.exception(),
                            "task": task,
                        }
                    )

            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            loop.close()

    try:
        loop.run_until_complete(runner())
    except KeyboardInterrupt:
        return None
    finally:
        _shutdown_loop()


async def soundcloud_test():
    with open(SECRETS_FILENAME, "r") as fp:
        secrets = json.load(fp)
    oauth_token = secrets["sc_oauth"]
    sc = await soundcloud.Client.create(oauth_token)

    await sc.close()

if __name__ == "__main__":
    main()
    # asyncio.run(soundcloud_test())
