import disnake
from datetime import datetime
from ..validator import TypedDict, without
from typing import Annotated

class Sketch(TypedDict):
    channel: disnake.TextChannel
    timestamp: Annotated[datetime, disnake.utils.utcnow]

    @without("channel")
    async def without_channel(self):
        pass
