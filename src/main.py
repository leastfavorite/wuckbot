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
        state_manifest = {}
        secrets_manifest = {
            "test_guilds": list[int],
            "bot_token": str,
            "admin": disnake.User
        }
        # import cogs (executing these once lets all classes get registered)
        for ext in disnake.utils.search_directory(COGS_FOLDER):
            ext_module = importlib.import_module(ext.removeprefix("src."))
            cogs.extend(c for c in ext_module.__dict__.values() if
                        isclass(c) and issubclass(c, commands.Cog))
            state_manifest.update(
                getattr(ext_module, "STATE_MANIFEST", {}))
            secrets_manifest.update(
                getattr(ext_module, "SECRETS_MANIFEST", {}))

        # load json
        await State.create(STATE_FILENAME, state_manifest, bot=bot)
        await Secrets.create(SECRETS_FILENAME, secrets_manifest, bot=bot)

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


async def soundcloud_test():
    with open(SECRETS_FILENAME, "r") as fp:
        secrets = json.load(fp)
        oauth = secrets["soundcloud_oauth"]

    from util import soundcloud
    session = await soundcloud.Session.create(oauth)
    # url = "https://cdn.discordapp.com/attachments/1214299973374713919/121534" \
    #     "5389826220083/walter_white_scream.wav?ex=6605a418&is=65f32f18&hm=02" \
    #     "d0c1b6d11fd803f893353abcad1386569bba8e6525367986934a3546ff49b9&"
    # json_ = await session.upload_track(url, title="fortnite song", description="heyyyy :p", tags="fortnitecore")
    # print(json.dumps(json_, indent=2))
    url = "https://soundcloud.com/least_favorite/fortnite-song-7/s-DvZspJB94eR"
    track = await session.fetch_track(url)
    await track.edit(title="cool awesome song 12")
    await session.close()
    pass

if __name__ == "__main__":
    main()
    # import asyncio
    # asyncio.run(soundcloud_test())
