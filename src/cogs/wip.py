import disnake
from disnake.ext import commands

from util import embeds
from util.wip import Wip
from util.decorators import error_handler, UserError

from typing import Optional
from functools import wraps

from inspect import signature

from util.json import State

STATE_MANIFEST = {
    "wips": list[Wip]
}


def _wip_wrapper(f):
    @wraps(f)
    async def _inner(self, inter: disnake.AppCmdInter, *args, **kwargs):
        wip = disnake.utils.get(State().wips, channel=inter.channel)
        if wip is None:
            raise UserError("You are not in a WIP channel.")
        return await f(self, inter, wip, *args, **kwargs)

    # hack the __annotations__ so that the state/role values
    # dont show to the slash_command registration decorator
    sig = signature(f, follow_wrapped=True)
    parameters = list(sig.parameters.values())
    parameters.pop(2)
    sig = sig.replace(parameters=tuple(parameters))
    _inner.__signature__ = sig

    return _inner


class WipCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(
        dm_permission=False,
        default_member_permissions=disnake.Permissions.none())
    async def wip(self, inter: disnake.AppCommandInteraction):
        pass

    @wip.sub_command(description="Joins a user to this WIP")
    @error_handler
    @_wip_wrapper
    async def join(self,
                   inter: disnake.AppCommandInteraction,
                   wip: Wip,
                   user: disnake.Member):

        if wip.role in user.roles:
            raise UserError(f"{user.mention} is already in this WIP!")

        await user.add_roles(wip.role)
        await inter.response.send_message(
            ephemeral=True,
            embed=embeds.success(
                f"{user.mention} added. Use `/wip credit` to credit them."
            ))

    @wip.sub_command(description="Leaves this WIP")
    @error_handler
    @_wip_wrapper
    async def leave(self,
                    inter: disnake.AppCommandInteraction,
                    wip: Wip,
                    user: Optional[disnake.Member] = None):

        if user is None:
            await inter.author.remove_roles(wip.role)
            await inter.send(embed=embeds.success(
                "You have been removed from this WIP."), ephemeral=True)
            return

        if wip.role not in user.roles:
            raise UserError(f"{user.mention} is not in this WIP!")
        await user.remove_roles(wip.role)
        await inter.response.send_message(
            ephemeral=True,
            embed=embeds.success(
                f"{user.mention} removed. Use `/wip credit` to remove credit."
            ))

    @wip.sub_command(description="Changes the title of this WIP")
    @error_handler
    @_wip_wrapper
    async def title(self,
                    inter: disnake.AppCommandInteraction,
                    wip: Wip,
                    title: str,
                    progress: Optional[commands.Range(int, 0, 100)] = None):
        await inter.response.defer(with_message=True, ephemeral=True)
        await wip.edit(name=title, progress=progress)
        await inter.followup.send(ephemeral=True, embed=embeds.success(
            f"Title successfully changed to \"{title}\"."))

    @wip.sub_command(description="Changes the progress level of this WIP")
    @error_handler
    @_wip_wrapper
    async def progress(self,
                       inter: disnake.AppCommandInteraction,
                       wip: Wip,
                       progress: commands.Range(int, 0, 100)):
        await inter.response.defer(with_message=True, ephemeral=True)
        await wip.edit(progress=progress)
        await inter.followup.send(ephemeral=True, embed=embeds.success(
            f"Progress updated to `{progress}%`!"))

    @wip.sub_command(description="Adds/removes credit for a user.")
    @error_handler
    @_wip_wrapper
    async def credit(self,
                     inter: disnake.ApplicationCommandInteraction,
                     wip: Wip,
                     credit_type: str = commands.Param(
                         choices=["vocalist", "producer"]),
                     user: Optional[disnake.Member] = None):
        await inter.response.defer(with_message=True, ephemeral=True)

        if user is None:
            user = inter.author

        credit_list = wip.credit.vocalists if credit_type == "vocalist" \
            else wip.credit.producers

        if user in credit_list:
            credit_list.remove(user)
            await wip.update_pinned()
            response = f"{user.mention} removed as a {credit_type}."
            if user == inter.author:
                response = f"You have been removed as a {credit_type}."
        else:
            credit_list.append(user)
            await wip.update_pinned()
            response = f"{user.mention} added as a {credit_type}."
            if user == inter.author:
                response = f"You have been added as a {credit_type}."

        await inter.followup.send(ephemeral=True,
                                  embed=embeds.success(response))


def setup(bot):
    bot.add_cog(WipCog(bot))
