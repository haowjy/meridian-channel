"""CLI command handlers for hooks.* operations."""

from collections.abc import Callable
from functools import partial
from typing import Annotated, Any

from cyclopts import App, Parameter

from meridian.cli.registration import register_manifest_cli_group
from meridian.lib.hooks.types import HookEventName
from meridian.lib.ops.hooks import (
    HookCheckInput,
    HookListInput,
    HookRunInput,
    hooks_check_sync,
    hooks_list_sync,
    hooks_run_sync,
)

Emitter = Callable[[Any], None]


def _hooks_list(emit: Emitter) -> None:
    emit(hooks_list_sync(HookListInput()))


def _hooks_check(emit: Emitter) -> None:
    output = hooks_check_sync(HookCheckInput())
    emit(output)
    if not output.ok:
        raise SystemExit(1)


def _hooks_run(
    emit: Emitter,
    name: Annotated[
        str,
        Parameter(help="Hook name to execute manually."),
    ],
    event: Annotated[
        HookEventName | None,
        Parameter(
            name="--event",
            help="Optional event context to simulate (for example: spawn.finalized).",
        ),
    ] = None,
) -> None:
    emit(hooks_run_sync(HookRunInput(name=name, event=event)))


def register_hooks_commands(app: App, emit: Emitter) -> tuple[set[str], dict[str, str]]:
    """Register hooks CLI commands using manifest metadata as source of truth."""

    handlers: dict[str, Callable[[], Callable[..., None]]] = {
        "hooks.list": lambda: partial(_hooks_list, emit),
        "hooks.check": lambda: partial(_hooks_check, emit),
        "hooks.run": lambda: partial(_hooks_run, emit),
    }
    return register_manifest_cli_group(
        app,
        group="hooks",
        handlers=handlers,
        command_help_epilogues={
            "hooks.run": (
                "Examples:\n\n"
                "  meridian hooks run git-autosync\n\n"
                "  meridian hooks run git-autosync --event spawn.finalized\n\n"
                "`hooks run` bypasses interval throttling for manual execution."
            )
        },
        emit=emit,
        default_handler=partial(_hooks_list, emit),
    )
