from disnake.ext import commands
import disnake

import asyncio
import aiohttp

from ..utils import UserError, embeds, buttons, get_audio_attachment
from ..datatypes import Wip, Update
from ..filemethods import state
from .. import soundcloud

UPDATE_REACTION = "\N{BELL}"

STATE_MANIFEST = {
    "soundclouds": dict[disnake.User, soundcloud.User]
}


class UpdateCog(commands.Cog):
    def __init__(self,
                 bot: commands.InteractionBot, sc: soundcloud.Client):
        self.bot = bot
        self.sc = sc
        self.update_lock = asyncio.Lock()

    @commands.Cog.listener("on_message")
    async def on_message(self, message: disnake.Message):
        # if a guild message is sent
        if not message.guild:
            return

        # by someone else
        if message.author == message.guild.me:
            return

        # with an audio attachment
        if not get_audio_attachment(message):
            return

        # in a wip channel
        if not disnake.utils.get(state().wips, channel__id=message.channel.id):
            return

        # react with a bell!
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
        wip = disnake.utils.get(state().wips, channel__id=e.channel_id)
        if wip is None:
            return

        # with an audio attachment
        msg: disnake.Message = await wip.channel.fetch_message(e.message_id)
        if not msg.attachments or \
                not msg.attachments[0].content_type or \
                not msg.attachments[0].content_type.startswith("audio"):
            return

        # by someone the webcage role
        author = await wip.channel.guild.get_or_fetch_member(e.user_id)
        if not author:
            return None

        if disnake.utils.get(author.roles, name="webcage") is None:
            return

        async with self.update_lock:

            # and we haven't updated with this message before
            if wip.update \
                    and wip.update.file \
                    and wip.update.file.id == msg.id:
                return

            def check(e_: disnake.RawReactionActionEvent):
                assert(author)
                return e_.user_id == author.id and \
                    str(e_.emoji) == UPDATE_REACTION

            # and they don't un-react within 3 seconds
            async with wip.channel.typing():
                try:
                    # we loop here because we have to handle a situation like
                    # this:
                    # - user a reacts
                    # - user b reacts
                    # - user a unreacts
                    # and correctly determine the person who requested the
                    # update.
                    while True:
                        await self.bot.wait_for(
                            "raw_reaction_remove",
                            check=check, timeout=3)
                        # we didn't time out, there's a reaction removal
                        print("hi!")

                        # see if anyone else reacted
                        msg = await wip.channel.fetch_message(e.message_id)
                        bells = disnake.utils.get(
                            msg.reactions, emoji=UPDATE_REACTION)
                        if not bells:
                            return

                        # find non-bot user in bells and run again
                        async for user in bells.users():
                            # we found a non-bot user
                            if user != wip.guild.me:
                                assert isinstance(user, disnake.Member)
                                author = user
                                break
                        else:
                            # all reactions were removed
                            return

                # message got deleted
                except disnake.NotFound:
                    return
                # reaction didn't get removed
                except asyncio.TimeoutError:
                    pass

            # update
            await self.create_update(author=author, file_msg=msg, wip=wip)

    # TODO update to new error handler
    async def create_update(self,
                            author: disnake.Member,
                            file_msg: disnake.Message,
                            wip: Wip):
        # send embed
        embed = disnake.Embed(
            color=disnake.Color.blue(),
            title="Updating..."
        )
        embed.set_footer(
            text=f"{author.global_name} requested this update.",
            icon_url=embeds.WUCK
        )
        reply = await file_msg.reply(embed=embed)

        async def edit_status(msg: str):
            embed.description = msg
            await reply.edit(embed=embed)

        guild = author.guild

        async def remove_author_reaction():
            if not (wip.update and wip.update.file == file_msg.id):
                try:
                    await file_msg.remove_reaction(
                        emoji=UPDATE_REACTION, member=author)
                except disnake.NotFound:
                    pass

        try:
            # get wips playlist
            wips_playlist = None
            async for pl in self.sc.me.playlists():
                if pl.title.lower() == "wips":
                    wips_playlist = pl
                    break
            else:
                raise UserError("Could not find a playlist named 'wips'.")

            # get updates channel
            updates_channel = disnake.utils.get(
                guild.text_channels, name="updates")
            if updates_channel is None:
                raise UserError("Could not find a #updates channel.")

            await edit_status(
                "Getting SoundCloud accounts for credited members...")
            # generate soundcloud description
            description = wip.soundcloud_description()

            # if we ended up with members w/o linked soundcloud, fail
            # until they link themselves
            wip.raise_on_unlinked_members()

            if wip.track:
                await edit_status("Deleting old track...")
                try:
                    await wip.track.delete()
                except aiohttp.ClientResponseError as e:
                    if e.status != 404:
                        raise e

            # upload to soundcloud
            await edit_status("Uploading new track...")

            wip.track = await self.sc.upload_track(
                file_url=file_msg.attachments[0].url,
                title=wip.name,
                description=description,
                tags="wip"
            )
            await wips_playlist.add_track(wip.track, top=True)

            # send update message to #updates
            await edit_status(f"Sending to {updates_channel.mention}...")

            embed = wip.update_embed()

            update_msg = await updates_channel.send(
                embed=embed,
                components=[
                    buttons.wip_join(wip),
                    buttons.track_link(wip.track)
                ]
            )

            # send file in a separate message (just looks a bit better, imo)
            file = await file_msg.attachments[0].to_file()
            await update_msg.reply(file=file)

            # save!
            wip.update = Update(
                file=file_msg,
                message=update_msg,
                timestamp=disnake.utils.utcnow()
            )

            # update pinned
            await wip.update_pinned()

            await reply.edit(embed=embeds.success(
                f"Update requested by {author.mention} was successful.\n"
                f"[View it here.]({update_msg.jump_url})"))

        except UserError as e:
            embed = embeds.error(e.args[0])
            await remove_author_reaction()
            await reply.edit(embed=embed)

        except Exception as e:
            embed = embeds.error(
                f"Unknown exception ({type(e).__name__}) raised. Tell Aria!")
            await reply.edit(embed=embed)
            await remove_author_reaction()
            raise e
