from disnake.ext import commands
import disnake

from ..utils import error_handler, UserError, embeds, buttons
from .. import soundcloud, state

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

        wip = disnake.utils.get(state().wips, channel__id=channel_id)
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
        num_wips = len(state().wips)
        if index < 0:
            index = 0
        if index >= num_wips:
            index = num_wips - 1

        wip = state().wips[index]

        # add to WIP
        if wip.role in inter.author.roles:
            await inter.author.remove_roles(wip.role)
            followup = f"You have been removed from `{wip.name}`."
        else:
            await inter.author.add_roles(wip.role)
            followup = f"You have been added to {wip.channel.mention}."

        # update components
        components = inter.message.components

        def replace_component(component):
            if component.custom_id.startswith("wiptoggle"):
                return buttons.wip_toggle(wip, inter.author)
            else:
                if component.type != disnake.ComponentType.button:
                    raise NotImplementedError(
                        "wip toggle is not powerful enough!")
                return disnake.ui.Button.from_component(component)

        components = [[
            replace_component(c) for c in row.children] for row in components]

        await inter.response.edit_message(components=components)
        await inter.followup.send(ephemeral=True,
                                  embed=embeds.success(followup))

    async def handle_wip_view(self,
                              inter: disnake.MessageInteraction,
                              index: int):
        # keep index within bounds
        num_wips = len(state().wips)
        if index < 0:
            index = 0
        if index >= num_wips:
            index = num_wips - 1

        wip = state().wips[index]

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

    # channel remove (check if wip)
    @commands.Cog.listener("on_guild_channel_delete")
    async def on_channel_remove(self, channel: disnake.abc.GuildChannel):
        wip = disnake.utils.get(state().wips, channel=channel)
        if not wip:
            return
        assert(isinstance(channel, disnake.TextChannel))

        await wip.without_channel()
        state().wips = [wip for wip in state().wips if wip.channel != channel]

    # role remove (check if wip)
    @commands.Cog.listener("on_guild_role_delete")
    async def on_role_remove(self, role: disnake.Role):
        wip = disnake.utils.get(state().wips, role=role)
        if not wip:
            return

        await wip.reconstruct_role()

    # channel name change (check if wip)
    @commands.Cog.listener("on_guild_channel_update")
    async def on_channel_update(self, channel: disnake.abc.GuildChannel):
        wip = disnake.utils.get(state().wips, channel=channel)
        if not wip:
            return
        assert(isinstance(channel, disnake.TextChannel))

        if channel.name != wip._get_channel_name(wip.name, wip.progress):
            await wip.edit()

    # user leaves (check if credited)
    @commands.Cog.listener("on_raw_member_remove")
    async def on_member_remove(self, evt: disnake.RawGuildMemberRemoveEvent):
        user = evt.user if isinstance(evt.user, disnake.User) else evt.user._user
        if not user.mutual_guilds:
            for wip in state().wips:
                needs_update = False

                if user in wip.credit.producers:
                    wip.credit.producers.remove(user)
                    needs_update = True

                if user in wip.credit.vocalists:
                    wip.credit.vocalists.remove(user)
                    needs_update = True

                if needs_update:
                    embed = disnake.Embed(
                        color=disnake.Color.blurple(),
                        title="User left the server",
                        description=
                            f"The user `{user.name}` has left the server. "
                            "Since this bot has no way to store information "
                            "about users outside the server, their credit "
                            "on this song has been removed.")

                    embed.set_footer(icon_url=embeds.WUCK,
                                     text=embeds.success().footer.text)
                    await wip.channel.send(embed=embed)
                    await wip.edit()

        state().links = [x for x in state().links if x.discord != user]

    # message deleted (check if pinned)
    # message deleted (check if most recent update)
    @commands.Cog.listener("on_raw_message_delete")
    async def on_message_delete(self, evt: disnake.RawMessageDeleteEvent):
        pinned_wip = disnake.utils.get(state().wips, pinned__id=evt.message_id)
        update_wip = disnake.utils.get(
            state().wips, update__message__id=evt.message_id)

        if pinned_wip:
            await pinned_wip.update_pinned()

        if update_wip:
            update_wip.update = None
            await update_wip.edit()

    # integration, baby!
