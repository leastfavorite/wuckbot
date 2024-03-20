from disnake.ext import commands
import disnake

from typing import Optional

from util.wip import Wip
from util.decorators import error_handler, UserError
from util import embeds

from util.json import State

STATE_MANIFEST = {
    "wips": list[Wip]
}


class WipsCog(commands.Cog):
    def __init__(self, bot: commands.InteractionBot):
        self.bot = bot

    @commands.slash_command(
        dm_permission=False,
        default_member_permissions=disnake.Permissions.none())
    async def wips(self, inter: disnake.AppCommandInteraction):
        pass

    @wips.sub_command(description="Toggles access to all WIP channels")
    @error_handler
    async def viewall(self, inter: disnake.AppCommandInteraction):
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

    @commands.Cog.listener("on_button_click")
    @error_handler
    async def on_button_click(self, inter: disnake.MessageInteraction):
        if inter.component.custom_id.startswith("wips_view_"):
            c_id = inter.component.custom_id.removeprefix("wips_view_")

            followup = None
            # toggle: toggle join/leave
            if c_id.startswith("toggle_"):
                index, channel_id = \
                    [int(x) for x in c_id.removeprefix("toggle_").split("_")]

                wip = disnake.utils.get(State().wips, channel__id=channel_id)
                if not wip:
                    raise UserError("Could not find this WIP.")
                if wip.role in inter.author.roles:
                    await inter.author.remove_roles(wip.role)
                else:
                    await inter.author.add_roles(wip.role)
                    followup = f"You have been added to {wip.channel.mention}."

            elif c_id.startswith("move_"):
                index = int(c_id.removeprefix("move_"))

            else:
                raise UserError(
                    "You pressed an unknown button, somehow. What?")

            kwargs = {
                "embed": State().wips[index].view_embed(),
                "components": self.get_view_components(inter.author, index)
            }
            await inter.response.edit_message(**kwargs)

            if followup:
                await inter.followup.send(ephemeral=True,
                                          embed=embeds.success(followup))

    @staticmethod
    async def view_autocomplete(inter: disnake.AppCommandInteraction,
                                user_input: str):
        wips = [wip.name for wip in State().wips]
        return [name for name in wips if user_input.lower() in name.lower()]

    def get_view_components(self, author: disnake.Member, index: int):
        wip: Wip = State().wips[index]
        num_wips = len(State().wips)
        join_wip_button = disnake.ui.Button(
            label="Leave",
            emoji="\N{DASH SYMBOL}",
            style=disnake.ButtonStyle.danger,
            custom_id=f"wips_view_toggle_{index}_{wip.channel.id}"
        )
        if wip.role not in author.roles:
            join_wip_button = disnake.ui.Button(
                label="Join",
                emoji="\N{MICROPHONE}",
                style=disnake.ButtonStyle.primary,
                custom_id=f"wips_view_toggle_{index}_{wip.channel.id}"
            )

        return [
            disnake.ui.Button(
                emoji="\N{BLACK LEFT-POINTING DOUBLE TRIANGLE}",
                disabled=(index == 0),
                style=disnake.ButtonStyle.secondary,
                custom_id=f"wips_view_move_{index - 1}"
            ),
            join_wip_button,
            disnake.ui.Button(
                emoji="\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE}",
                disabled=(index == num_wips - 1),
                style=disnake.ButtonStyle.secondary,
                custom_id=f"wips_view_move_{index + 1}"
            )
        ]

    @wips.sub_command(description="Shows information about WIPs")
    @error_handler
    async def view(
            self,
            inter: disnake.AppCommandInteraction,
            wip: Optional[str] = commands.Param(
                autocomplete=view_autocomplete)):
        if wip:
            index = [wip.name.lower() for wip in State().wips].index(
                wip.lower())
        else:
            index = len(State().wips) - 1

        wip = State().wips[index]
        await inter.response.send_message(
            ephemeral=True,
            embed=wip.view_embed(),
            components=self.get_view_components(inter.author, index))

    @staticmethod
    async def join_autocomplete(inter: disnake.AppCommandInteraction,
                                user_input: str):
        # only get WIPs the author is not in
        roles = inter.author.roles
        wips = [wip.name for wip in State().wips if wip.role not in roles]

        return [name for name in wips if user_input.lower() in name.lower()]

    @wips.sub_command(description="Joins a WIP")
    @error_handler
    async def join(
            self,
            inter: disnake.AppCommandInteraction,
            wip: str = commands.Param(autocomplete=join_autocomplete)):
        wip = disnake.utils.get(State().wips, name=wip)
        if wip is None:
            raise UserError("Could not find that WIP.")
        if wip.role in inter.author.roles:
            raise UserError("You're already in that WIP!")
        await inter.author.add_roles(wip.role)
        await inter.response.send_message(
            ephemeral=True, embed=embeds.success(
                f"You have been added to {wip.channel.mention}.\n"
                f"Use `/wip leave from within the channel to leave."))
