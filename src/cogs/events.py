from disnake.ext import commands
import disnake

from datatypes import State
from utils import error_handler, UserError, embeds, buttons
import soundcloud

class EventCog(commands.Cog):
    def __init__(self, bot: commands.InteractionBot, sc: soundcloud.Client):
        self.bot = bot
        self.sc = sc

    @commands.Cog.listener("on_button_click")
    @error_handler()
    async def on_button_click(self, inter: disnake.MessageInteraction):
        name, *args = inter.component.custom_id.split("|")

        if name == "wipjoin":
            channel_id, = args
            return await self.handle_wip_join(inter, int(channel_id))

        if name == "wiptoggle":
            channel_id, = args
            return await self.handle_wip_toggle(inter, int(channel_id))

        if name == "wipview":
            index, = args
            return await self.handle_wip_view(inter, int(index))

        if name == "trackdelete":
            s_id, token = args
            return await self.handle_track_delete(inter, int(s_id), token)

    async def handle_wip_join(self,
                              inter: disnake.MessageInteraction,
                              channel_id: int):

        wip = disnake.utils.get(State().wips, channel__id=channel_id)
        if not wip:
            raise UserError("This WIP no longer exists.")

        if wip.role in inter.author.roles:
            raise UserError(
                f"You already have access to {wip.channel.mention}")

        await inter.author.add_roles(wip.role)

        await inter.response.send_message(
            ephemeral=True,
            embed=embeds.success(
                f"You have been added to {wip.channel.mention}.\n"
                f"To leave, use `/wip leave` from within its channel.")
        )

    async def handle_wip_toggle(self,
                                inter: disnake.MessageInteraction,
                                index: int):

        # keep index within bounds
        num_wips = len(State().wips)
        if index < 0:
            index = 0
        if index >= num_wips:
            index = num_wips - 1

        wip = State().wips[index]

        # add to WIP
        if wip.role in inter.author.roles:
            await inter.author.remove_roles(wip.role)
            followup = f"You have been removed from `{wip.name}`."
        else:
            await inter.author.add_roles(wip.role)
            followup = f"You have been added to {wip.channel.mention}."

        # update components
        msg = await inter.original_response()
        comp = msg.components
        indices = [i for (i, c) in enumerate(comp)
                   if c.custom_id.startswith("wiptoggle")]
        for i in indices:
            comp[i] = buttons.wip_toggle(wip, inter.author)

        await inter.response.edit_message(components=comp)
        await inter.followup.send(ephemeral=True,
                                  embed=embeds.success(followup))

    async def handle_wip_view(self,
                              inter: disnake.MessageInteraction,
                              index: int):
        # keep index within bounds
        num_wips = len(State().wips)
        if index < 0:
            index = 0
        if index >= num_wips:
            index = num_wips - 1

        wip = State().wips[index]

        components = [
            buttons.wip_view_prev(index - 1),
            buttons.wip_toggle(wip, inter.author),
            buttons.wip_view_next(index + 1)
        ]

        # TODO replace with as_embed
        embed = await wip.view_embed()

        await inter.response.edit_message(
            embed=embed,
            components=components)

    async def handle_track_delete(self,
                                  inter: disnake.MessageInteraction,
                                  s_id: int, token: str):
        track = await self.sc.fetch_track(s_id, token)
        if not track:
            raise UserError("Track not found! Maybe it was already deleted?")

        title = track.title
        await track.delete()

        # delete the "delete" button
        msg = await inter.original_response()
        comp = [c for c in msg.components
                if not c.custom_id.startswith("trackdelete")]

        await inter.response.edit_message(components=comp)

        await inter.followup.send(
            embed=embeds.success(
                f"{inter.author.mention} chose to delete "
                f"`{title}` from SoundCloud.")
        )

    # TODO:

    # channel remove (check if wip)
    # role remove (check if wip)
    # channel name change (check if wip)
    # user leaves (check if credited)
    # message deleted (check if pinned)
    # message deleted (check if most recent update)

    # integration, baby!!
