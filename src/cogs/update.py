from disnake.ext import commands
import disnake

import asyncio

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
        if not author or \
                disnake.utils.get(author.roles, name="webcage") is None:
            return

        async with self.update_lock:

            # and we haven't updated with this message before
            if wip.update \
                    and wip.update.file \
                    and wip.update.file.id == msg.id:
                return

            # and they don't un-react within 3 seconds
            async with wip.channel.typing():
                await asyncio.sleep(3)
                bells = disnake.utils.get(msg.reactions, emoji=UPDATE_REACTION)
                if not bells or bells.count < 2:
                    return

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

        try:
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
            unlinked = wip.unlinked_members()
            if unlinked:
                mentions = "\n".join(m.mention for m in unlinked)
                raise UserError(
                    f"Unknown SoundCloud profiles for these users:\n"
                    f"{mentions}\n"
                    f"Use `/linksc` to register them."
                )

            if wip.track:
                await edit_status("Deleting old track...")
                await wip.track.delete()

            # upload to soundcloud
            await edit_status("Uploading new track...")

            wip.track = await self.sc.upload_track(
                file_url=file_msg.attachments[0].url,
                title=wip.name,
                description=description,
                tags="wip"
            )

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
            await updates_channel.send(file=file)

            # save!
            wip.update = Update(
                file=file_msg,
                update=update_msg,
                timestamp=disnake.utils.utcnow()
            )

            # update pinned
            await wip.update_pinned()

            await reply.edit(embed=embeds.success(
                f"Update requested by {author.mention} was successful.\n"
                f"[View it here.]({update_msg.jump_url})"))

        except UserError as e:
            embed = embeds.error(e.args[0])
            await reply.edit(embed=embed)
        except Exception as e:
            embed = embeds.error(
                f"Unknown exception ({type(e).__name__}) raised. Tell Aria!")
            await reply.edit(embed=embed)
            raise e
