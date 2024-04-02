import disnake
from datetime import datetime
from ..validator import TypedDict
from typing import Annotated

class Sketch(TypedDict):
    channel: disnake.TextChannel
    timestamp: Annotated[datetime, disnake.utils.utcnow]
