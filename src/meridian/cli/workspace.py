"""CLI command handlers for workspace.* operations."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Annotated, Any

from cyclopts import App, Parameter

from meridian.lib.ops.registry import get_all_operations
from meridian.lib.ops.workspace import (
    WorkspaceCloseInput,
    WorkspaceListInput,
    WorkspaceResumeInput,
    WorkspaceShowInput,
    WorkspaceStartInput,
    workspace_close_sync,
    workspace_list_sync,
    workspace_resume_sync,
    workspace_show_sync,
    workspace_start_sync,
)


def _workspace_start(
    emit: Any,
    name: Annotated[
        str | None,
        Parameter(name="--name", help="Optional workspace name."),
    ] = None,
    model: Annotated[
        str,
        Parameter(name="--model", help="Model id or alias for workspace harness."),
    ] = "",
    autocompact: Annotated[
        int | None,
        Parameter(name="--autocompact", help="Auto-compact threshold in messages."),
    ] = None,
    dry_run: Annotated[
        bool,
        Parameter(name="--dry-run", help="Preview launch command without starting harness."),
    ] = False,
    harness_args: Annotated[
        tuple[str, ...],
        Parameter(
            name="--harness-arg",
            help="Additional harness arguments (repeatable).",
            negative_iterable=(),
        ),
    ] = (),
) -> None:
    emit(
        workspace_start_sync(
            WorkspaceStartInput(
                name=name,
                model=model,
                autocompact=autocompact,
                dry_run=dry_run,
                harness_args=harness_args,
            )
        )
    )


def _workspace_resume(
    emit: Any,
    workspace: Annotated[
        str | None,
        Parameter(name="--workspace", help="Workspace id to resume."),
    ] = None,
    fresh: Annotated[
        bool,
        Parameter(name="--fresh", help="Start a new harness process before resume."),
    ] = False,
    model: Annotated[
        str,
        Parameter(name="--model", help="Override model id or alias."),
    ] = "",
    autocompact: Annotated[
        int | None,
        Parameter(name="--autocompact", help="Auto-compact threshold in messages."),
    ] = None,
    harness_args: Annotated[
        tuple[str, ...],
        Parameter(
            name="--harness-arg",
            help="Additional harness arguments (repeatable).",
            negative_iterable=(),
        ),
    ] = (),
) -> None:
    emit(
        workspace_resume_sync(
            WorkspaceResumeInput(
                workspace=workspace,
                fresh=fresh,
                model=model,
                autocompact=autocompact,
                harness_args=harness_args,
            )
        )
    )


def _workspace_list(
    emit: Any,
    limit: Annotated[
        int,
        Parameter(name="--limit", help="Maximum number of workspaces to return."),
    ] = 10,
) -> None:
    emit(workspace_list_sync(WorkspaceListInput(limit=limit)))


def _workspace_show(emit: Any, workspace: str) -> None:
    emit(workspace_show_sync(WorkspaceShowInput(workspace=workspace)))


def _workspace_close(emit: Any, workspace: str) -> None:
    emit(workspace_close_sync(WorkspaceCloseInput(workspace=workspace)))


def register_workspace_commands(app: App, emit: Any) -> tuple[set[str], dict[str, str]]:
    handlers: dict[str, Callable[[], Callable[..., None]]] = {
        "workspace.start": lambda: partial(_workspace_start, emit),
        "workspace.resume": lambda: partial(_workspace_resume, emit),
        "workspace.list": lambda: partial(_workspace_list, emit),
        "workspace.show": lambda: partial(_workspace_show, emit),
        "workspace.close": lambda: partial(_workspace_close, emit),
    }

    registered: set[str] = set()
    descriptions: dict[str, str] = {}

    for op in get_all_operations():
        if op.cli_group != "workspace" or op.mcp_only:
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
