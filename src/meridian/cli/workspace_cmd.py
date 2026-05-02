"""CLI command handlers for workspace operations."""

from collections.abc import Callable
from functools import partial
from typing import Annotated, Any

from cyclopts import App, Parameter

from meridian.cli.ext_registration import register_extension_cli_group
from meridian.lib.extensions.registry import get_first_party_registry
from meridian.lib.ops.workspace import WorkspaceMigrateInput, workspace_migrate_sync

Emitter = Callable[[Any], None]


def _workspace_migrate(
    emit: Emitter,
    force: Annotated[
        bool,
        Parameter(
            name="--force",
            help="Replace existing [workspace] entries in meridian.local.toml.",
        ),
    ] = False,
) -> None:
    emit(workspace_migrate_sync(WorkspaceMigrateInput(force=force)))


def register_workspace_commands(app: App, emit: Emitter) -> tuple[set[str], dict[str, str]]:
    # workspace commands have no required CLI args — handlers are auto-generated.
    handlers: dict[str, Callable[[], Callable[..., None]]] = {
        "meridian.workspace.migrate": lambda: partial(_workspace_migrate, emit),
    }
    return register_extension_cli_group(
        app,
        registry=get_first_party_registry(),
        group="workspace",
        handlers=handlers,
        command_help_epilogues={
            "meridian.workspace.init": (
                "Create or update local workspace config (meridian.local.toml).\n\n"
                "The file is local-only and scaffolded with commented [workspace.NAME] examples.\n"
                "The command is idempotent and also ensures local gitignore coverage.\n\n"
                "Examples:\n\n"
                "  meridian workspace init\n"
            ),
            "meridian.workspace.migrate": (
                "Migrate legacy workspace.local.toml entries into meridian.local.toml.\n\n"
                "By default the command aborts if meridian.local.toml already contains "
                "[workspace] entries. Use --force to replace existing local workspace entries.\n\n"
                "Examples:\n\n"
                "  meridian workspace migrate\n"
                "  meridian workspace migrate --force\n"
            )
        },
        emit=emit,
    )
