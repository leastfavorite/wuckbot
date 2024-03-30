import disnake
from disnake.ext import commands

from utils import embeds, error_handler, UserError, send_modal
from datatypes import Wip, State
import soundcloud

from typing import Optional
from functools import wraps

from inspect import signature

STATE_MANIFEST = {
    "wips": list[Wip]
}


def _wip_wrapper(f):
    @wraps(f)
    async def _inner(self, inter: disnake.ApplicationCommandInteraction,
                     *args, **kwargs):
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
    def __init__(self,
                 bot: commands.InteractionBot,
                 sc: soundcloud.Client):
        self.bot = bot
        self.sc = sc

    @commands.slash_command(
        dm_permission=False,
        default_member_permissions=disnake.Permissions.none())
    async def wip(self, inter: disnake.ApplicationCommandInteraction):
        pass

    @wip.sub_command()
    @error_handler
    @_wip_wrapper
    async def join(self,
                   inter: disnake.ApplicationCommandInteraction,
                   wip: Wip,
                   user: disnake.Member):
        """
        Joins another user to this WIP.
        Parameters
        -----------
        user: The user to join.
        """

        if wip.role in user.roles:
            raise UserError(f"{user.mention} is already in this WIP!")

        await user.add_roles(wip.role)
        await inter.response.send_message(
            ephemeral=True,
            embed=embeds.success(
                f"{user.mention} added. Use `/wip credit` to credit them."
            ))

    @wip.sub_command()
    @error_handler
    @_wip_wrapper
    async def leave(self,
                    inter: disnake.ApplicationCommandInteraction,
                    wip: Wip,
                    user: Optional[disnake.Member] = None):
        """
        Leaves a WIP, or removes another user.

        Parameters
        -----------
        user: The user to remove. Default is yourself.
        """

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

    @wip.sub_command()
    @error_handler
    @_wip_wrapper
    async def title(self,
                    inter: disnake.ApplicationCommandInteraction,
                    wip: Wip,
                    title: str):
        """
        Updates a song's title across Discord and SoundCloud.

        Parameters
        -----------
        title: The new title.
        """
        await inter.response.defer(with_message=True, ephemeral=True)
        await wip.edit(name=title)
        await inter.followup.send(ephemeral=True, embed=embeds.success(
            f"Title successfully changed to \"{title}\"."))

    @wip.sub_command()
    @error_handler
    @_wip_wrapper
    async def progress(self,
                       inter: disnake.ApplicationCommandInteraction,
                       wip: Wip,
                       progress: commands.Range[int, 0, 100]):
        """
        Updates a song's progress across Discord and SoundCloud.

        Parameters
        -----------
        progress: The current progress, as a percentage.
        """
        await inter.response.defer(with_message=True, ephemeral=True)
        await wip.edit(progress=progress)
        await inter.followup.send(ephemeral=True, embed=embeds.success(
            f"Progress updated to `{progress}%`!"))

    @wip.sub_command()
    @error_handler
    @_wip_wrapper
    async def credit(self,
                     inter: disnake.ApplicationCommandInteraction,
                     wip: Wip,
                     credit_type: str = commands.Param(
                         choices=["vocalist", "producer"]),
                     user: Optional[disnake.Member] = None):
        """
        Credits a user on a WIP.

        Parameters
        -----------
        credit_type: The type of credit to bestow.
        user: The user to give credit to.
        """
        if user is None:
            user = inter.author

        credit_list = wip.credit.vocalists if credit_type == "vocalist" \
            else wip.credit.producers

        if user in credit_list:
            credit_list.remove(user)
            response = f"{user.mention} removed as a {credit_type}."
            if user == inter.author:
                response = f"You have been removed as a {credit_type}."
        else:
            # check if soundcloud is available
            if user not in State().soundclouds:
                await self.link_soundcloud(inter, user)

            credit_list.append(user)
            response = f"{user.mention} added as a {credit_type}."
            if user == inter.author:
                response = f"You have been added as a {credit_type}."

        # this forces an update of all embeds + soundcloud
        await wip.edit()
        await inter.response.send_message(
            ephemeral=True, embed=embeds.success(response))

    async def link_soundcloud(self,
                              inter: disnake.ApplicationCommandInteraction,
                              user: disnake.User):
        response = await send_modal(
            inter, ephemeral=True,
            title=f"Link {user.name}'s SoundCloud",
            components=[disnake.ui.TextInput(
                label="SoundCloud Link",
                placeholder="https://soundcloud.com/skrillex",
                custom_id="link",
                required=True
            )]
        )

        sc_user = await self.sc.resolve(response.link)
        if type(sc_user) is not soundcloud.User:
            raise UserError("Could not resolve the provided link.")

        # we need to map the underlying user,
        # people will have the same sc accounts no matter which
        # server
        if type(user) is disnake.Member:
            State().soundclouds[user._user] = sc_user
        else:
            State().soundclouds[user] = sc_user

        return sc_user

    @commands.slash_command(
        dm_permission=False,
        default_member_permissions=disnake.Permissions.none())
    @error_handler
    async def linksc(self, inter: disnake.ApplicationCommandInteraction,
                     user: Optional[disnake.User] = None):
        """
        Links a Discord account to its owner's SoundCloud.

        Parameters
        -----------
        user: The user to link.
        """
        if user is None:
            user = inter.author
        sc_user = await self.link_soundcloud(inter, user)

        await inter.response.send_message(
            ephemeral=True,
            embed=embeds.success(
                f"Linked {user.mention}'s [SoundCloud]({sc_user.url}).")
        )


def setup(bot):
    bot.add_cog(WipCog(bot))
