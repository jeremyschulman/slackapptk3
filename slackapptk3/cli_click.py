# -----------------------------------------------------------------------------
# System Imports
# -----------------------------------------------------------------------------

from typing import Optional, Coroutine
import asyncio
from functools import wraps
from contextvars import ContextVar

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

import click
from click import decorators
from click import Command, Option, Group, Context
from click.globals import get_current_context
from slackapptk3.response import Response
from slackapptk3.request.command import CommandRequest
from first import first
import pyee

# -----------------------------------------------------------------------------
#
#                                 CODE BEGINS
#
# -----------------------------------------------------------------------------

click_context = ContextVar("click_context")

# -----------------------------------------------------------------------------
#
#                                 CODE BEGINS
#
# -----------------------------------------------------------------------------


def version_option(version=None, *param_decls, **attrs):
    async def send_version(ctx, message):
        rqst: CommandRequest = ctx.obj["rqst"]
        await Response(rqst).send(text=message)

    def decorator(f):
        prog_name = attrs.pop("prog_name", None)
        message = attrs.pop("message", "%(prog)s, version %(version)s")

        def callback(ctx, param, value):  # noqa
            if not value or ctx.resilient_parsing:
                return
            prog = prog_name
            if prog is None:
                prog = ctx.find_root().info_name

            asyncio.create_task(
                send_version(ctx, (message % {"prog": prog, "version": version}))
            )
            ctx.exit()

        attrs.setdefault("is_flag", True)
        attrs.setdefault("expose_value", False)
        attrs.setdefault("is_eager", True)
        attrs.setdefault("help", "Show the version and exit.")
        attrs["callback"] = callback
        return decorators.option(*(param_decls or ("--version",)), **attrs)(f)

    return decorator


async def slack_send_usage_help(ctx: Context, errmsg: Optional[str] = None):
    help_text = ctx.get_help()
    rqst: CommandRequest = ctx.obj["rqst"]
    resp = Response(rqst)

    atts = resp["attachments"] = list()
    try_cmd = f"{rqst.rqst_data['command']} {rqst.rqst_data['text']}"
    user_id = rqst.user_id

    if errmsg:
        atts.append(
            dict(
                color="#FF0000",  # red
                pretext=f"Hi <@{user_id}>, I could not run your command",
                text=f"```{try_cmd}```",
                fallback=try_cmd,
            )
        )

        atts.append(dict(text=f"```{errmsg}```", fallback=errmsg))

    atts.append(
        dict(pretext="Command help", text=f"```{help_text}```", fallback=help_text)
    )

    await resp.send()


async def slack_send_help(ctx: Context):
    help_text = ctx.get_help()
    rqst: CommandRequest = ctx.obj["rqst"]
    resp = Response(rqst)

    await resp.send(text=f"*Command help:*\n```{help_text}```", fallback=help_text)


class SlackClickHelper(Command):
    def __init__(self, *vargs, **kwargs):
        self.event_id = kwargs.get("name")
        super(SlackClickHelper, self).__init__(*vargs, **kwargs)

    def get_help_option(self, ctx):
        help_options = self.get_help_option_names(ctx)
        if not help_options or not self.add_help_option:
            return

        def slack_show_help(_ctx: click.Context, param, value):  # noqa
            if value and not _ctx.resilient_parsing:
                asyncio.create_task(slack_send_help(_ctx))
                _ctx.exit()

        return Option(
            help_options,
            is_flag=True,
            is_eager=True,
            expose_value=False,
            callback=slack_show_help,
            help="Show this message and exit.",
        )

    def invoke(self, ctx):
        """
        return the coroutine ready for await, but cannot await here ...
        execution deferred to the `run` method that is async.
        """
        click_context.set(ctx)
        return super().invoke(ctx)

    async def run(self, rqst, **_extras):
        args = rqst.rqst_data["text"].split()
        ctx_obj = dict(rqst=rqst, args=args)

        try:
            # Call the Click main method for this Command/Group instance.  The
            # result will either be that a handler returned a coroutine for
            # async handling, or there is an Exception that needs to be
            # handled.

            cli_coro = self.main(
                args=args, prog_name=self.name, obj=ctx_obj, standalone_mode=False
            )

            if isinstance(cli_coro, Coroutine):
                return await cli_coro

        except click.exceptions.BadOptionUsage as exc:
            ctx = self.make_context(self.name, args, obj=ctx_obj)
            await slack_send_usage_help(ctx, errmsg=exc.format_message())
            return

        except click.exceptions.MissingParameter as exc:
            ctx = exc.ctx or click_context.get()
            await slack_send_usage_help(ctx, errmsg=exc.format_message())
            return

        except click.exceptions.UsageError as exc:
            ctx = exc.ctx or click_context.get()
            await slack_send_usage_help(ctx, errmsg=exc.show())
            return

        except click.exceptions.Exit:
            return


class SlackClickCommand(SlackClickHelper, Command):
    pass


class SlackClickGroup(SlackClickHelper, Group):
    def __init__(self, *vargs, **kwargs):
        self.ic = pyee.EventEmitter()
        kwargs["invoke_without_command"] = True
        super(SlackClickGroup, self).__init__(*vargs, **kwargs)

    @staticmethod
    def as_async_group(f):
        orig_callback = f.callback

        @wraps(f)
        def new_callback(*vargs, **kwargs):
            ctx = get_current_context()
            if ctx.invoked_subcommand:
                return

            # presume the orig_callback was defined as an async def.  Therefore
            # defer the execution of the coroutine to the calling main.
            return orig_callback(*vargs, **kwargs)

        f.callback = new_callback
        return f

    def add_command(self, cmd, name=None):
        # need to wrap Groups in async handler since the underlying Click code
        # is assuming sync processing.
        cmd.event_id = f"{self.event_id}.{name or cmd.name}"

        if isinstance(cmd, SlackClickGroup):
            cmd = self.as_async_group(cmd)

        super(SlackClickGroup, self).add_command(cmd, name)

    def command(self, *args, **kwargs):
        kwargs["cls"] = SlackClickCommand
        return super().command(*args, **kwargs)

    def group(self, *args, **kwargs):
        kwargs["cls"] = SlackClickGroup
        return super().group(*args, **kwargs)

    def on(self, cmd: SlackClickCommand):
        def wrapper(f):
            self.ic.on(cmd.event_id, f)

        return wrapper

    async def emit(self, rqst, event):
        handler = first(self.ic.listeners(event))

        if handler is None:
            rqst.app.log.critical(f"No handler for command option '{event}'")
            return

        return await handler(rqst)
