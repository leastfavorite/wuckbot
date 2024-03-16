import disnake
from types import SimpleNamespace


async def send_modal(inter: disnake.ApplicationCommandInteraction,
                     *args, ephemeral: bool = True, **kwargs):
    await inter.response.send_modal(*args, **kwargs)
    custom_id = kwargs["custom_id"]

    modal_inter: disnake.ModalInteraction = await inter.bot.wait_for(
        "modal_submit",
        check=lambda i: i.custom_id == custom_id and
        i.author.id == inter.author.id,
        timeout=600
    )

    await modal_inter.response.defer(with_message=True, ephemeral=ephemeral)
    inter.response = modal_inter.response
    inter.followup = modal_inter.followup
    return SimpleNamespace(**modal_inter.text_values)
