import disnake
from typing import Optional, Any
from functools import wraps

import inspect
import traceback

import asyncio

from .embeds import error, success, WUCK

def Secrets():
    from ..datatypes import Secrets
    return Secrets()

__all__ = [
    'UserError',
    'UserSuccess',
]

def _updates_channel(guild: disnake.Guild) -> Optional[disnake.TextChannel]:
    return disnake.utils.get(guild.text_channels, name="updates")

async def send_error(guild: Optional[disnake.Guild], **kwargs):
    if guild and (channel := _updates_channel(guild)):
        await channel.send(**kwargs)
        return
    await Secrets().admin.send(**kwargs)

# Represents an error caused by malformed user input.
class UserError(Exception):
    pass

# Represents a successful interaction from a user.
class UserSuccess(Exception):
    pass

async def send_exception_embed(
        e: Exception, guild: Optional[disnake.Guild] = None,
        author: Optional[disnake.User] = None, command: Optional[str] = None,
        suppress = (asyncio.TimeoutError,)):

    tb_text = "".join(traceback.format_exception(e))

    embed = disnake.Embed(
        color=disnake.Color.red(),
        title=f"{type(e).__name__} raised",
        description=f"```{tb_text}```")

    if author is not None:
        embed.add_field("Executor", author.mention)
    if command is not None:
        embed.add_field("Command", command)

    content = ""

    admin = Secrets().admin
    if not guild:
        await admin.send(embed=embed)
        return

    footer = ""
    channel = disnake.utils.get(guild.text_channels, name="bot-errors")
    if not channel:
        footer += "Make a #bot-errors channel! "

    admin = Secrets().admin
    if guild not in admin.mutual_guilds:
        footer += "Where is your admin?"
    else:
        content = admin.mention

    embed.set_footer(text=footer, icon_url=WUCK)

    if channel:
        await channel.send(content=content, embed=embed)
    elif admin:
        await admin.send(content=content, embed=embed)
    else:
        raise RuntimeError("No place to put exception embed!")


async def exc_embed(e: Exception,
                 guild: Optional[disnake.Guild] = None,
                 author: Optional[disnake.User] = None,
                 command: Optional[str] = None) -> Optional[disnake.Embed]:
    if isinstance(e, UserError):
        return error(e.args[0])
    if isinstance(e, UserSuccess):
        return success(e.args[0])
    if isinstance(e, asyncio.TimeoutError):
        return None
    await send_exception_embed(e, guild=guild, author=author, command=command)
    return error(
        "An unknown error has occured. An admin has been notified.")

def error_handler(ephemeral: bool = True):
    def _deco(f):
        @wraps(f)
        async def _inner(*args: Any, **kwargs):
            sig = inspect.signature(f)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            first_arg = None
            for param in sig.parameters.values():
                if param.name not in ["self", "cls"]:
                    first_arg = bound_args.arguments[param.name]
                    break

            inter: disnake.Interaction = None
            if isinstance(first_arg, disnake.Interaction):
                inter = first_arg

            try:
                retval = await f(*args, **kwargs)
                return retval

            except Exception as e:

                # can't find first_arg, so we really have no way of
                # responding to this directly
                # exc_embed will send an exception embed if necessary
                if first_arg is None:
                    await exc_embed(e)
                    if not isinstance(e, (UserError, UserSuccess, asyncio.TimeoutError)):
                        raise e
                    return

                # try fetching this stuff
                guild = getattr(first_arg, 'guild', None)
                author = None
                command = None
                respond = None

                # checks if a potential "respond" hook actually matters--
                def is_valid_response(f):
                    if f is None:
                        return False

                    if not asyncio.iscoroutinefunction(f):
                        return False

                    sig = inspect.signature(f)
                    return 'embed' in sig.parameters.keys()

                # most likely scenario is that we get an interaction,
                # which we parse here
                if inter:
                    guild = inter.guild
                    author = inter.author
                    if isinstance(inter,
                                  disnake.ApplicationCommandInteraction):
                        command = inter.application_command.qualified_name

                    if inter.response.is_done():
                        respond = inter.followup.send
                    else:
                        respond = inter.response.send_message
                else:
                    # otherwise, we try to find a send command
                    # that's awaitable and takes an embed

                    # first, try sending to first_arg.send
                    if (send := getattr(first_arg, 'send', None)) \
                            and is_valid_response(send):
                        respond = send

                    # otherwise, try finding a channel first
                    elif (channel := getattr(first_arg, 'channel', None)):
                        if (send := getattr(channel, 'send', None)) \
                                and is_valid_response(send):
                            respond = send

                embed = await exc_embed(
                    e, guild=guild, author=author, command=command)

                if respond:
                    sig = inspect.signature(respond)
                    supports_ephemeral = 'ephemeral' in sig.parameters.keys()

                    try:
                        if supports_ephemeral:
                            await respond(embed=embed, ephemeral=ephemeral)
                        else:
                            await respond(embed=embed)
                    except Exception:
                        # swallow.. if we fail here, it just means we tried
                        # sending to a deleted channel or something.
                        # we'll still get error messages forwarded
                        pass

                if not isinstance(
                        e, (UserError, UserSuccess, asyncio.TimeoutError)):
                    raise e
        return _inner
    return _deco
