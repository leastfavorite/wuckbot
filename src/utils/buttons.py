from typing import TYPE_CHECKING

from .. import soundcloud, state

if TYPE_CHECKING:
    from ..datatypes import Wip


import disnake
def wip_join(wip: 'Wip'):
    return disnake.ui.Button(
        label="Join",
        emoji="\N{MICROPHONE}",
        style=disnake.ButtonStyle.primary,
        custom_id=f"wipjoin|{wip.channel.id}")

def wip_toggle(wip: 'Wip', user: disnake.Member):
    in_wip = wip.role in user.roles

    if in_wip:
        return disnake.ui.Button(
            label="Leave",
            emoji="\N{DASH SYMBOL}",
            style=disnake.ButtonStyle.danger,
            custom_id=f"wiptoggle|{wip.channel.id}")
    else:
        return disnake.ui.Button(
            label="Join",
            emoji="\N{MICROPHONE}",
            style=disnake.ButtonStyle.primary,
            custom_id=f"wiptoggle|{wip.channel.id}")

def wip_view_prev(index: int):
    return disnake.ui.Button(
        emoji="\N{BLACK LEFT-POINTING DOUBLE TRIANGLE}",
        disabled=(index < 0),
        style=disnake.ButtonStyle.secondary,
        custom_id=f"wipview|{index}")

def wip_view_next(index: int):
    num_wips = len(state().wips)
    return disnake.ui.Button(
        emoji="\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE}",
        disabled=(index >= num_wips),
        style=disnake.ButtonStyle.secondary,
        custom_id=f"wipview|{index}")

def track_link(track: soundcloud.Track):
    return disnake.ui.Button(
        label="SoundCloud",
        emoji="\N{SPEAKER WITH THREE SOUND WAVES}",
        style=disnake.ButtonStyle.link,
        url=track.url)

def track_delete(track: soundcloud.Track):
    return disnake.ui.Button(
        label="Delete on SoundCloud",
        emoji="\N{WASTEBASKET}",
        style=disnake.ButtonStyle.danger,
        custom_id=f"trackdelete|{track.s_id}|{track.secret_token}")
