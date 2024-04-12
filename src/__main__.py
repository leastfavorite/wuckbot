import disnake
from disnake.ext import commands

import json
import asyncio

from inspect import signature

from .datatypes import Tokens, Config, State
from . import validator, soundcloud, cogs

CONFIG_FILENAME = "config.json"
STATE_FILENAME = "state.json"
TOKENS_FILENAME = "tokens.json"

def main():
    loop = asyncio.new_event_loop()

    # we have to hack some initialization stuff out of the config files
    # because we can't get it as a fancy object until the bot is started
    with open(CONFIG_FILENAME, "r") as fp:
        config = json.load(fp)
    guild = config["guild"]

    with open(TOKENS_FILENAME, "r") as fp:
        tokens = json.load(fp)
    discord_token = tokens["discord"]
    soundcloud_token = tokens["soundcloud"]

    del config, tokens

    intents = disnake.Intents.default()
    intents.members = True
    intents.message_content = True

    bot = commands.InteractionBot(
        intents=intents,
        test_guilds=[guild],
        loop=loop)

    on_close = []
    async def _on_ready():
        sc = await soundcloud.Client.create(soundcloud_token)
        on_close.append(sc.close())

        registrar = validator.Registrar(
            *validator.base_serializers(),
            *validator.disnake_serializers(bot),
            *soundcloud.serializers(sc)
        )

        # load json
        await State.load(STATE_FILENAME, "backups/state", registrar)
        on_close.append(State().save())

        await Config.load(CONFIG_FILENAME, "backups/config", registrar)
        on_close.append(Config().save())

        await Tokens.load(TOKENS_FILENAME, "backups/tokens", registrar)
        on_close.append(Tokens().save())

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
            await bot.start(token=discord_token)
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
    with open(TOKENS_FILENAME, "r") as fp:
        tokens = json.load(fp)
    oauth_token = tokens["soundcloud"]
    sc = await soundcloud.Client.create(oauth_token)

    await sc.close()

if __name__ == "__main__":
    main()
    # asyncio.run(soundcloud_test())
