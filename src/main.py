import disnake
import json
from disnake.ext import commands

from util.watchdog import get_watchdog

# from cogs.wips import WipCog
from cogs.wipify import WipifyCog
from cogs.wip import WipCog

import util.decorators

# get secrets (just a json file)
with open("secrets.json", "r") as fp:
    secrets = json.load(fp)
util.decorators.set_admin_id(secrets["admin_id"])

# get state database (just an updating json file)
state = get_watchdog("config.json", {})

# setup bot
intents = disnake.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.InteractionBot(
    intents=intents, test_guilds=secrets["test_guilds"])

# add cogs
# bot.add_cog(WipCog(bot, state))
bot.add_cog(WipifyCog(bot, state))
bot.add_cog(WipCog(bot, state))

bot.run(token=secrets["bot_token"])
