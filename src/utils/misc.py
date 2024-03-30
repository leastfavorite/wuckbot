import disnake
from types import SimpleNamespace
from secrets import token_hex
from typing import Optional

async def send_modal(inter: disnake.ApplicationCommandInteraction,
                     *args, ephemeral: bool = True, **kwargs):
    kwargs.setdefault("custom_id", token_hex(32))
    await inter.response.send_modal(*args, **kwargs)

    modal_inter: disnake.ModalInteraction = await inter.bot.wait_for(
        "modal_submit",
        check=lambda i: i.custom_id == kwargs["custom_id"] and
        i.author.id == inter.author.id,
        timeout=600
    )

    inter.response = modal_inter.response
    inter.followup = modal_inter.followup
    return SimpleNamespace(**modal_inter.text_values)

def get_audio_attachment(message: disnake.Message) -> Optional[disnake.Attachment]:
    if not message.attachments:
        return None

    attachment = message.attachments[0]
    if not attachment.content_type:
        return None

    if attachment.content_type.startswith('audio'):
        return attachment

    return None
