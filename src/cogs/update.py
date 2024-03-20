from disnake.ext import commands
import disnake

import asyncio
from typing import Optional

from util.wip import Wip, Update
from util.decorators import error_handler, UserError
from util import embeds

from util.json import State
from util import soundcloud

UPDATE_REACTION = "\N{BELL}"

STATE_MANIFEST = {
    "soundclouds": dict[disnake.User, soundcloud.User]
}


class UpdateCog(commands.Cog):
    def __init__(self, bot: commands.InteractionBot, sc: soundcloud.Session):
        self.bot = bot
        self.sc = sc

    @commands.Cog.listener("on_message")
    async def on_message(self, message: disnake.Message):
        # don't worry about bot messages
        if message.author == message.guild.me:
            return

        # don't worry about messages without audio attachments
        if len(message.attachments) == 0 or \
                not message.attachments[0].content_type.startswith("audio"):
            return

        # don't worry about messages outside a WIP channel
        wip = disnake.utils.get(State().wips, channel__id=message.channel.id)
        if wip is None:
            return

        await message.add_reaction(UPDATE_REACTION)

    @commands.Cog.listener("on_raw_reaction_add")
    async def on_raw_reaction_add(self,
                                  e: disnake.RawReactionActionEvent):
        # if we get a bell emoji reaction
        if str(e.emoji) != UPDATE_REACTION:
            return

        # by someone else
        if e.user_id == self.bot.user.id:
            return

        # in a wip channel
        wip: Wip = disnake.utils.get(State().wips, channel__id=e.channel_id)
        if wip is None:
            return

        # with an audio attachment
        msg: disnake.Message = await wip.channel.fetch_message(e.message_id)
        if len(msg.attachments) == 0 or \
                not msg.attachments[0].content_type.startswith("audio"):
            return

        # and we haven't updated with this message before
        if disnake.utils.get(wip.updates, file__id=msg.id):
            return

        async with wip.channel.typing():
            # and the reaction isn't removed
            await asyncio.sleep(3)
            bells = disnake.utils.get(msg.reactions, emoji=UPDATE_REACTION)
            if bells.count < 2:
                # someone hit the reaction and then chickened out
                return

            # (we get the author here to avoid a race condition afterward)
            author = await wip.channel.guild.get_or_fetch_member(e.user_id)

            # and we haven't updated with this message before
            if disnake.utils.get(wip.updates, file__id=msg.id):
                return

        await self.create_update(author=author, file_msg=msg, wip=wip)

    async def create_update(self,
                            author: disnake.Member,
                            file_msg: disnake.Message,
                            wip: Wip):
        # get updates channel
        updates_channel = disnake.utils.get(
            author.guild.text_channels, name="updates")
        if updates_channel is None:
            raise UserError("Could not find a #updates channel.")

        # we put in a placeholder to make sure we don't accidentally
        # update twice
        update = Update(
            file=file_msg,
            update=None,
            timestamp=disnake.utils.utcnow())
        wip.updates.append(update)

        reply = await file_msg.reply(embed=embeds.success(
            f"{author.mention} has requested an update."))

        # upload to soundcloud

        # send update message to #updates
        file = await file_msg.attachments[0].to_file()
        update_msg = await updates_channel.send(file=file)
        update.update = update_msg

        # update pinned
