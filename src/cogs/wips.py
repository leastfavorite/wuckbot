from disnake.ext import commands
import disnake

from typing import Optional

from ..utils import error_handler, UserError, embeds, buttons
from ..datatypes import Wip
from .. import state

class WipsCog(commands.Cog):
    def __init__(self, bot: commands.InteractionBot):
        self.bot = bot

    @commands.slash_command(
        dm_permission=False,
        default_member_permissions=disnake.Permissions.none())
    async def wips(self, inter: disnake.AppCommandInteraction):
        pass

    @wips.sub_command()
    @error_handler()
    async def viewall(self, inter: disnake.AppCommandInteraction):
        """
        Toggles access to all WIP channels.
        """
        view_wips_role = disnake.utils.get(inter.guild.roles, name="view wips")
        if view_wips_role is None:
            raise UserError("Couldn't find a role called 'view wips'")

        if view_wips_role in inter.author.roles:
            await inter.author.remove_roles(view_wips_role)
            await inter.response.send_message(
                ephemeral=True, embed=embeds.success(
                    "You are no longer viewing all WIPs."))

        else:
            await inter.author.add_roles(view_wips_role)
            await inter.response.send_message(
                ephemeral=True, embed=embeds.success(
                    "You are now viewing all WIPs."))

    @staticmethod
    async def view_autocomplete(inter: disnake.AppCommandInteraction,
                                user_input: str):
        wips = [wip.name for wip in state().wips]
        return [name for name in wips if user_input.lower() in name.lower()]

    def get_view_components(self, author: disnake.Member, index: int):
        wip: Wip = state().wips[index]
        num_wips = len(state().wips)

        return [
            buttons.wip_view_prev(index - 1),
            buttons.wip_toggle(wip, author),
            buttons.wip_view_next(index + 1)
        ]

    @wips.sub_command()
    @error_handler()
    async def view(
            self,
            inter: disnake.AppCommandInteraction,
            wip: Optional[str] = commands.Param(
                default=None,
                autocomplete=view_autocomplete)):
        """
        Opens an index of all WIPs, with option to join each one.

        Parameters
        ----------
        wip: The WIP to view. Defaults to the newest one.
        """
        if wip:
            index = [wip.name.lower() for wip in state().wips].index(
                wip.lower())
        else:
            index = len(state().wips) - 1

        wip = state().wips[index]
        await inter.response.send_message(
            ephemeral=True,
            embed=wip.view_embed(),
            components=self.get_view_components(inter.author, index))

    @staticmethod
    async def join_autocomplete(inter: disnake.AppCommandInteraction,
                                user_input: str):
        # only get WIPs the author is not in
        roles = inter.author.roles
        wips = [wip.name for wip in state().wips if wip.role not in roles]

        return [name for name in wips if user_input.lower() in name.lower()]

    @wips.sub_command()
    @error_handler()
    async def join(
            self,
            inter: disnake.AppCommandInteraction,
            wip: str = commands.Param(autocomplete=join_autocomplete)):
        """
        Joins a WIP you're not a part of.

        Parameters
        ----------
        wip: The WIP to join.
        """
        real_wip = disnake.utils.get(state().wips, name=wip)
        if real_wip is None:
            raise UserError("Could not find that WIP.")
        if real_wip.role in inter.author.roles:
            raise UserError("You're already in that WIP!")
        await inter.author.add_roles(real_wip.role)
        await inter.response.send_message(
            ephemeral=True, embed=embeds.success(
                f"You have been added to {real_wip.channel.mention}.\n"
                f"Use `/wip leave from within the channel to leave."))
