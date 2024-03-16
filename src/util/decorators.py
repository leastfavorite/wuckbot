import disnake
from disnake.ext import commands
from functools import wraps
import traceback
import asyncio

import util.embeds as embeds
from util.json import Secrets


class UserError(Exception):
    pass


def error_handler(f):
    @wraps(f)
    async def _inner(self,
                     inter: disnake.ApplicationCommandInteraction,
                     *args, **kwargs):
        try:
            return await user_error_handler(f)(self, inter, *args, **kwargs)
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            # format embed
            traceback_text = traceback.format_tb(e.__traceback__)
            executor = inter.author.mention
            command = inter.application_command.qualified_name

            embed = disnake.Embed(
                color=disnake.Color.red(),
                title=f"{type(e).__name__} raised",
                description=f"```{traceback_text}```"
            )

            embed.add_field("Executor", executor)
            embed.add_field("Command", command)

            # get admin/channel
            admin: disnake.User = Secrets().admin
            if inter.guild not in admin.mutual_guilds:
                admin = None

            err_channel = disnake.utils.get(
                inter.guild.text_channels, name="bot-errors")
            footer = ""
            if err_channel is None:
                err_channel = inter.channel
                footer += "Make a #bot-errors channel! "

            if admin is None:
                footer += "Where is Aria?"

            embed.set_footer(text=footer)

            content = "" if admin is None else admin.mention
            # send embed
            await err_channel.send(content=content, embed=embed)

            # send error response to inter
            user_embed = embeds.error(
                "An unknown error has occured. An admin has been notified.")
            if inter.response.is_done():
                await inter.followup.send(
                    ephemeral=True, embed=user_embed)
            else:
                await inter.response.send_message(
                    ephemeral=True, embed=user_embed)
            raise e
    return _inner


def user_error_handler(f):
    @wraps(f)
    async def _inner(self,
                     inter: disnake.ApplicationCommandInteraction,
                     *args, **kwargs):
        try:
            return await f(self, inter, *args, **kwargs)
        except UserError as e:
            embed = embeds.error(e.args[0])
            if inter.response.is_done():
                await inter.followup.send(ephemeral=True, embed=embed)
            else:
                await inter.response.send_message(ephemeral=True, embed=embed)
            return None
    return _inner
