from disnake.ext import commands, tasks
import disnake
from datetime import datetime, timedelta
import calendar

import asyncio
from ..utils import embeds, error_handler, UserError, get_audio_attachment
from ..filemethods import state
from ..datatypes import Wip, Sketch
from .. import soundcloud

class ArchiveCog(commands.Cog):
    def __init__(self, bot: commands.InteractionBot, sc: soundcloud.Client):
        self.bot = bot
        self.last_loop: datetime = disnake.utils.utcnow()
        self.loop.start()

    @staticmethod
    def add_time(dt: datetime, months: int = 0, days: int = 0) -> datetime:
        for _ in range(months):
            _, days_in_month = calendar.monthrange(dt.year, dt.month)
            dt = dt + timedelta(days=days_in_month)
        return dt + timedelta(days=days)

    # pester wips after some amounts of time without updates:
    async def pester_wips(self, time):
        for wip in state().wips:
            dt = wip.update.timestamp if wip.update else wip.timestamp

            pester_times = [
                ("will be archived in 1 day",  self.add_time(dt, months=6, days=-1)),
                ("will be archived in 3 days", self.add_time(dt, months=6, days=-3)),
                ("will be archived in 1 week", self.add_time(dt, months=6, days=-7)),
                ("has been inactive for 5 months", self.add_time(dt, months=5)),
                ("has been inactive for 3 months", self.add_time(dt, months=3)),
                ("has been inactive for 1 month",  self.add_time(dt, months=1)),
                ("has been inactive for 2 weeks",  self.add_time(dt, days=14)),
                ("has been inactive for 1 week",   self.add_time(dt, days=7)),
                ("has been inactive for 3 days",   self.add_time(dt, days=3))
            ]

            for time_str, pester_time in pester_times:
                if self.last_loop < pester_time <= time:
                    embed = disnake.Embed(
                        color=disnake.Color.yellow(),
                        title=f"\N{HOURGLASS} This WIP {time_str} \N{HOURGLASS}",
                        timestamp = dt,
                        description="If a WIP remains inactive for 6 months, it "
                                    "will be archived.\nTo reset the timer, "
                                    "post a new update.\n"
                                    "To archive the song now, use `/archive`.")
                    embed.set_footer(icon_url=embeds.WUCK, text="Last Update")

                    await wip.channel.send(
                        content=wip.role.mention,
                        embed=embed
                    )

                    break

    # pester sketch after 2 days
    async def pester_sketches(self, time):
        for sketch in state().sketches:
            if self.last_loop < self.add_time(sketch.timestamp, days=2) <= time:
                embed = disnake.Embed(
                    color=disnake.Color.yellow(),
                    title="\N{HOURGLASS} This sketch will be archived in 1 day \N{HOURGLASS}",
                    timestamp=sketch.timestamp,
                    description="Sketches are archived after 3 days of inactivity.\n"
                                "To reset the timer, post an audio file in the chat.\n"
                                "To archive the sketch now, use `/archive`.\n"
                                "To turn it into a WIP, use `/wipify`.")
                embed.set_footer(icon_url=embeds.WUCK, text="Last Update")

                await sketch.channel.send(
                    content="@here",
                    embed=embed
                )

    # archive wip after 6 months
    async def archive_wips(self, time):
        for wip in state().wips:
            timestamp = wip.update.timestamp if wip.update else wip.timestamp
            if self.add_time(timestamp, months=6) <= time:
                await self.archive_wip(wip)

    # archive sketch after 3 days
    async def archive_sketches(self, time):
        for sketch in state().sketches:
            if self.add_time(sketch.timestamp, days=3) <= time:
                await self.archive_sketch(sketch)

    @tasks.loop(hours=1.0)
    async def loop(self):
        time = disnake.utils.utcnow()
        await asyncio.gather(
            self.pester_wips(time),  self.pester_sketches(time),
            self.archive_wips(time), self.archive_sketches(time))
        self.last_loop = time

    @loop.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()

    async def archive_wip(self, wip: Wip):
        archive_category = disnake.utils.find(
            lambda c: c.name.lower() == "archive", wip.guild.categories)
        if not archive_category:
            raise UserError("Couldn't find a category called `archive`.")

        view_archive = disnake.utils.get(wip.guild.roles, name="view archive")
        if not view_archive:
            raise UserError("Couldn't find a role called `view archive`.")

        webcage_role = disnake.utils.get(wip.guild.roles, name="webcage")
        if not webcage_role:
            raise UserError("Couldn't find a role called `webcage`.")

        # remove wip from state
        state().wips = [w for w in state().wips if w.channel != wip.channel]

        # if soundcloud track, move it to the archive playlist
        track = wip.track
        if track:
            archive_playlist = None
            wips_playlist = None
            async for pl in track.sc.me.playlists():
                if pl.title.lower() == "archive":
                    archive_playlist = pl
                if pl.title.lower() == "wips":
                    wips_playlist = pl

                if archive_playlist and wips_playlist:
                    break
            else:
                if not archive_playlist:
                    raise UserError(
                        "Could not find a playlist named 'archive'.")
                if not wips_playlist:
                    raise UserError(
                        "Could not find a playlist named 'wips'.")

            if track in wips_playlist:
                await wips_playlist.remove_track(track)

            await archive_playlist.add_track(track, top=True)

        # remove the wip role
        await wip.role.delete(reason="wip archival")

        # change permissions so only people with "view archives" role can access
        # move the channel to the archive category
        await wip.channel.edit(
            category=archive_category,
            overwrites={
                wip.guild.default_role: disnake.PermissionOverwrite(view_channel=False),
                webcage_role: disnake.PermissionOverwrite(
                    view_channel=False,
                    manage_channels=False),
                view_archive: disnake.PermissionOverwrite(view_channel=True)
            }
        )
        await wip.channel.move(offset=1, beginning=True)

        # create an embed in #updates
        updates = disnake.utils.get(
            wip.guild.text_channels, name="updates")
        if updates is None:
            raise UserError("Could not find a #updates channel.")

        await updates.send(embed=wip.archive_embed())

    async def archive_sketch(self, sketch: Sketch):
        # remove sketch from state
        state().sketches = [
            s for s in state().sketches if s.channel != sketch.channel]

        guild = sketch.channel.guild

        archive = disnake.utils.get(guild.text_channels, name="sketch-archive")
        if not archive:
            raise UserError("`#sketch-archive` channel does not exist.")

        e = "\N{OPEN FILE FOLDER}"
        embed = disnake.Embed(
            color=disnake.Color.blurple(),
            timestamp=sketch.timestamp,
            title=f"{e} Archived Sketch: {sketch.channel.name}")
        embed.set_footer(icon_url=embeds.WUCK,
                         text="Last Updated")

        thread_message = None
        thread = None

        contributors = set()
        async for message in sketch.channel.history(limit=1000):
            attachment = get_audio_attachment(message)
            if not attachment:
                continue

            contributors.add(message.author)

            if not thread:
                thread_message = await archive.send(embed=embed)
                thread = await thread_message.create_thread(
                    name=sketch.channel.name,
                    auto_archive_duration=10080,
                    reason="sketch archival")
            await thread.send(content=message.author.mention,
                              file=await attachment.to_file())

        if thread_message:
            embed.add_field(
                name="Contributors",
                value="\n".join(c.mention for c in contributors))
            await thread_message.edit(embed=embed)

        await sketch.channel.delete(reason="sketch archival")

    @commands.slash_command(
        dm_permission=False,
        default_member_permissions=disnake.Permissions.none())
    @error_handler()
    async def archive(self, inter: disnake.AppCommandInteraction):
        """
        Archives a WIP or sketch channel.
        """
        await inter.response.defer(ephemeral=True)

        if (wip := disnake.utils.get(state().wips, channel=inter.channel)):
            await self.archive_wip(wip)
            await inter.edit_original_response(
                embed=embeds.success(
                    "This WIP has been archived, "
                    f"as requested by {inter.author.mention}."))
            return

        if (sketch := disnake.utils.get(state().sketches, channel=inter.channel)):
            await self.archive_sketch(sketch)
            # channel gets deleted, so there's no way to really respond...
            return

        raise UserError(
            "This command must be run from a WIP or Sketch channel.")

    @commands.slash_command(
        dm_permission=False,
        default_member_permissions=disnake.Permissions.none())
    @error_handler()
    async def viewarchive(self, inter: disnake.ApplicationCommandInteraction):
        """
        Toggles access to archive channels.
        """
        view_archives_role = disnake.utils.get(inter.guild.roles, name="view archive")
        if view_archives_role is None:
            raise UserError("Couldn't find a role called `view archive`.")

        if view_archives_role in inter.author.roles:
            await inter.author.remove_roles(view_archives_role)
            await inter.response.send_message(
                ephemeral=True, embed=embeds.success(
                    "You are no longer viewing archived channels."))

        else:
            await inter.author.add_roles(view_archives_role)
            await inter.response.send_message(
                ephemeral=True, embed=embeds.success(
                    "You are now viewing archived channels."))
