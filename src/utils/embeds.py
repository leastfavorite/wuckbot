import disnake
from typing import Optional
from datetime import datetime
# provides some common embeds

# TODO selectable from config
WUCK = "https://cdn.discordapp.com/attachments/" \
       "742588983799840881/820412558594801684/wcvector.png"

def error(msg: str, title: str = "Error"):
    embed = disnake.Embed(
        color=disnake.Color.red(),
        title=f"\u26a0\ufe0f {title} \u26a0\ufe0f",
        description=msg)
    embed.set_footer(
        text="If you believe this to be an error, bully Aria about it.",
        icon_url=WUCK)
    return embed


def success(msg: str = ""):
    embed = disnake.Embed(
        color=disnake.Color.green(),
        title="Success",
        description=msg)
    embed.set_footer(text="\u00A9Webcage 2024-\u221E. Glory to the Company.",
                     icon_url=WUCK)
