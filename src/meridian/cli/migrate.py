"""CLI command handlers for migrate.* operations."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Annotated, Any

from cyclopts import App, Parameter

from meridian.lib.ops.migrate import MigrateRunInput, migrate_run_sync
from meridian.lib.ops.registry import get_all_operations

Emitter = Callable[[Any], None]


def _migrate_run(
    emit: Emitter,
    jsonl_path: Annotated[str | None, Parameter(name="--jsonl-path")] = None,
    apply_skill_migrations: Annotated[
        bool, Parameter(name="--apply-skill-migrations")
    ] = True,
    repo_root: Annotated[str | None, Parameter(name="--repo-root")] = None,
) -> None:
    emit(
        migrate_run_sync(
            MigrateRunInput(
                repo_root=repo_root,
                jsonl_path=jsonl_path,
                apply_skill_migrations=apply_skill_migrations,
            )
        )
    )


def register_migrate_commands(app: App, emit: Emitter) -> tuple[set[str], dict[str, str]]:
    """Register migrate commands from the operation registry."""

    handlers: dict[str, Callable[[], Callable[..., None]]] = {
        "migrate.run": lambda: partial(_migrate_run, emit),
    }

    registered: set[str] = set()
    descriptions: dict[str, str] = {}

    for op in get_all_operations():
        if op.cli_group != "migrate" or op.mcp_only:
            continue
        handler_factory = handlers.get(op.name)
        if handler_factory is None:
            raise ValueError(f"No CLI handler registered for operation '{op.name}'")
        handler = handler_factory()
        handler.__name__ = f"cmd_{op.cli_group}_{op.cli_name}"
        app.command(handler, name=op.cli_name, help=op.description)
        registered.add(f"{op.cli_group}.{op.cli_name}")
        descriptions[op.name] = op.description

    app.default(partial(_migrate_run, emit))
    return registered, descriptions
