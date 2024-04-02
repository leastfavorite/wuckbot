from disnake.ext import commands, tasks
import disnake
from datetime import datetime, timedelta, UTC
import calendar

import asyncio
from ..utils import embeds
from ..filemethods import state
from ..datatypes import Wip, Sketch

class ArchiveCog(commands.Cog):
    def __init__(self, bot: commands.InteractionBot):
        self.bot = bot
        self.last_loop: datetime = datetime.fromtimestamp(0, UTC)

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

            archive_time = self.add_time(dt, months=6)
            nice_pester_times = [
                ("has been inactive for 3 days",   self.add_time(dt, days=3)),
                ("has been inactive for 1 week",   self.add_time(dt, days=7)),
                ("has been inactive for 2 weeks",  self.add_time(dt, days=14)),
                ("has been inactive for 1 month",  self.add_time(dt, months=1)),
                ("has been inactive for 3 months", self.add_time(dt, months=3)),
                ("has been inactive for 5 months", self.add_time(dt, months=5)),
                ("will be archived in 1 week", archive_time - timedelta(days=7)),
                ("will be archived in 3 days", archive_time - timedelta(days=3)),
                ("will be archived in 1 day",  archive_time - timedelta(days=1))
            ]
            for time_str, time in nice_pester_times:
                if self.last_loop < time <= time:
                    embed = disnake.Embed(
                        color=disnake.Color.yellow(),
                        title=f"\N{HOURGLASS} This WIP {time_str} \N{HOURGLASS}",
                        timestamp = dt,
                        description="If a WIP remains inactive for 6 months, it "
                                    "will be archived. To reset the timer, "
                                    "post a new update.\n"
                                    "To archive the song now, use `/archive`.")
                    embed.set_footer(icon_url=embeds.WUCK, text="Last Update")

                    await wip.channel.send(
                        content=wip.role.mention,
                        embed=embed
                    )

    # pester sketch after 2 days
    async def pester_sketches(self, time):
        for sketch in state().sketches:
            if self.last_loop < sketch.timestamp + timedelta(days=2) <= time:
                embed = disnake.Embed(
                    color=disnake.Color.yellow(),
                    title="\N{HOURGLASS} This sketch will be archived in 1 day \N{HOURGLASS}",
                    timestamp=sketch.timestamp,
                    description="Sketches are archived after 3 days of inactivity. "
                                "To reset the timer, post an audio file in the chat.\n"
                                "To archive the sketch now, use `/archive`.\n"
                                "To turn it into a WIP, use `/wipify`.\n")
                embed.set_footer(icon_url=embeds.WUCK, text="Last Update")

                await sketch.channel.send(
                    content="@here",
                    embed=embed
                )

    # archive wip after 6 months
    async def archive_wips(self, time):
        for wip in state().wips:
            timestamp = wip.update.timestamp if wip.update else wip.timestamp
            if self.last_loop < self.add_time(timestamp, months=6) <= time:
                await self.archive_wip(wip)

    # archive sketch after 3 days
    async def archive_sketches(self, time):
        for sketch in state().sketches:
            if self.last_loop < sketch.timestamp + timedelta(days=3) <= time:
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
        # remove wip from state

        # TODO: if soundcloud track, move it to the archive playlist
        # remove the wip role
        # change permissions so only people with "view archives" role can access
        # move the channel to the archive category

        # create an embed in #updates
        pass

    async def archive_sketch(self, sketch: Sketch):
        # remove sketch from state

        # get all active users
        # (break this into misc, we use this in from_channel)

        # create an embed in the sketch-archive channel
        # create a new thread in the sketch-archive channel

        # send each audio file into that thread

        # send a message to #updates
        pass

    @commands.slash_command(
        dm_permission=False,
        default_member_permissions=disnake.Permissions.none())
    @error_handler()
    async def archive(self, inter: disnake.AppCommandInteraction):
        if (wip := disnake.utils.get(state().wips, channel=inter.channel)):
            await self.archive_wip(wip)
            return

        if (sketch := disnake.utils.get(state().sketches, channel=inter.channel)):
            await self.archive_sketch(sketch)
            return

        raise UserError(
            "This command must be run from a WIP or Sketch channel.")
