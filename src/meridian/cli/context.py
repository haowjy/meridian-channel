"""CLI command handlers for context.* operations."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Annotated, Any

from cyclopts import App, Parameter

from meridian.lib.ops.context import (
    ContextListInput,
    ContextPinInput,
    ContextUnpinInput,
    context_list_sync,
    context_pin_sync,
    context_unpin_sync,
)
from meridian.lib.ops.registry import get_all_operations

Emitter = Callable[[Any], None]


def _context_pin(
    emit: Emitter,
    file_path: str,
    workspace: Annotated[
        str | None,
        Parameter(name="--workspace", help="Workspace id to update."),
    ] = None,
) -> None:
    emit(context_pin_sync(ContextPinInput(file_path=file_path, workspace=workspace)))


def _context_unpin(
    emit: Emitter,
    file_path: str,
    workspace: Annotated[
        str | None,
        Parameter(name="--workspace", help="Workspace id to update."),
    ] = None,
) -> None:
    emit(context_unpin_sync(ContextUnpinInput(file_path=file_path, workspace=workspace)))


def _context_list(
    emit: Emitter,
    workspace: Annotated[
        str | None,
        Parameter(name="--workspace", help="Workspace id to inspect."),
    ] = None,
) -> None:
    emit(context_list_sync(ContextListInput(workspace=workspace)))


def register_context_commands(app: App, emit: Emitter) -> tuple[set[str], dict[str, str]]:
    handlers: dict[str, Callable[[], Callable[..., None]]] = {
        "context.pin": lambda: partial(_context_pin, emit),
        "context.unpin": lambda: partial(_context_unpin, emit),
        "context.list": lambda: partial(_context_list, emit),
    }

    registered: set[str] = set()
    descriptions: dict[str, str] = {}

    for op in get_all_operations():
        if op.cli_group != "context" or op.mcp_only:
            continue
        handler_factory = handlers.get(op.name)
        if handler_factory is None:
            raise ValueError(f"No CLI handler registered for operation '{op.name}'")
        handler = handler_factory()
        handler.__name__ = f"cmd_{op.cli_group}_{op.cli_name}"
        app.command(handler, name=op.cli_name, help=op.description)
        registered.add(f"{op.cli_group}.{op.cli_name}")
        descriptions[op.name] = op.description

    return registered, descriptions
