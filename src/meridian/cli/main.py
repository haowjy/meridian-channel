"""Cyclopts CLI entry point for meridian."""

from __future__ import annotations

import sys
from contextlib import suppress
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal, cast

from cyclopts import App, Parameter

from meridian import __version__
from meridian.cli.context import register_context_commands
from meridian.cli.diag import register_diag_commands
from meridian.cli.export import register_export_commands
from meridian.cli.migrate import register_migrate_commands
from meridian.cli.models_cmd import register_models_commands
from meridian.cli.output import OutputConfig, normalize_output_format
from meridian.cli.output import emit as emit_output
from meridian.cli.run import register_run_commands
from meridian.cli.skills_cmd import register_skills_commands
from meridian.cli.workspace import register_workspace_commands
from meridian.lib.config._paths import resolve_repo_root
from meridian.lib.workspace.launch import cleanup_orphaned_locks
from meridian.server.main import run_server

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True, slots=True)
class GlobalOptions:
    """Top-level options that apply to all commands."""

    output: OutputConfig
    yes: bool = False
    no_input: bool = False


_GLOBAL_OPTIONS: ContextVar[GlobalOptions | None] = ContextVar("_GLOBAL_OPTIONS", default=None)


def get_global_options() -> GlobalOptions:
    """Return parsed global options for current command."""

    default = GlobalOptions(output=OutputConfig(format="text"))
    return _GLOBAL_OPTIONS.get() or default


def emit(payload: object) -> None:
    """Write command output using current output format settings."""

    emit_output(payload, get_global_options().output)


def _extract_global_options(argv: Sequence[str]) -> tuple[list[str], GlobalOptions]:
    json_mode = False
    porcelain_mode = False
    output_format: str | None = None
    yes = False
    no_input = False
    cleaned: list[str] = []

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--json":
            json_mode = True
            i += 1
            continue
        if arg == "--no-json":
            i += 1
            continue
        if arg == "--porcelain":
            porcelain_mode = True
            i += 1
            continue
        if arg == "--no-porcelain":
            i += 1
            continue
        if arg == "--format":
            if i + 1 >= len(argv):
                raise SystemExit("--format requires a value")
            output_format = argv[i + 1]
            i += 2
            continue
        if arg.startswith("--format="):
            output_format = arg.partition("=")[2]
            i += 1
            continue
        if arg == "--yes":
            yes = True
            i += 1
            continue
        if arg == "--no-yes":
            i += 1
            continue
        if arg == "--no-input":
            no_input = True
            i += 1
            continue
        if arg == "--no-no-input":
            i += 1
            continue

        cleaned.append(arg)
        i += 1

    resolved = normalize_output_format(
        requested=output_format,
        json_mode=json_mode,
        porcelain_mode=porcelain_mode,
        stdout_is_tty=sys.stdout.isatty(),
    )
    return cleaned, GlobalOptions(output=OutputConfig(format=resolved), yes=yes, no_input=no_input)


app = App(
    name="meridian",
    help="Meridian orchestrator CLI",
    version=__version__,
    help_formatter="plain",
)


@app.default
def root(
    json_mode: Annotated[bool, Parameter(name="--json")] = False,
    output_format: Annotated[str | None, Parameter(name="--format")] = None,
    porcelain: Annotated[bool, Parameter(name="--porcelain")] = False,
    yes: Annotated[bool, Parameter(name="--yes")] = False,
    no_input: Annotated[bool, Parameter(name="--no-input")] = False,
) -> None:
    """Meridian root command with global options."""

    resolved = normalize_output_format(
        requested=output_format,
        json_mode=json_mode,
        porcelain_mode=porcelain,
        stdout_is_tty=sys.stdout.isatty(),
    )
    _GLOBAL_OPTIONS.set(
        GlobalOptions(output=OutputConfig(format=resolved), yes=yes, no_input=no_input)
    )
    app.help_print()


@app.command(name="serve")
def serve() -> None:
    """Start FastMCP server on stdio."""

    run_server()


workspace_app = App(name="workspace", help="Workspace lifecycle commands", help_formatter="plain")
run_app = App(name="run", help="Run management commands", help_formatter="plain")
skills_app = App(name="skills", help="Skills catalog commands", help_formatter="plain")
models_app = App(name="models", help="Model catalog commands", help_formatter="plain")
context_app = App(
    name="context", help="Workspace context pinning commands", help_formatter="plain"
)
diag_app = App(name="diag", help="Diagnostics commands", help_formatter="plain")

export_app = App(name="export", help="Export commands", help_formatter="plain")
migrate_app = App(name="migrate", help="Migration commands", help_formatter="plain")
completion_app = App(name="completion", help="Shell completion helpers", help_formatter="plain")


app.command(workspace_app, name="workspace")
app.command(run_app, name="run")
app.command(skills_app, name="skills")
app.command(models_app, name="models")
app.command(context_app, name="context")
app.command(diag_app, name="diag")
app.command(export_app, name="export")
app.command(migrate_app, name="migrate")
app.command(completion_app, name="completion")


def _emit_completion(shell: str) -> None:
    normalized = _normalize_completion_shell(shell)
    print(app.generate_completion(shell=normalized))


def _normalize_completion_shell(shell: str) -> Literal["bash", "zsh", "fish"]:
    normalized = shell.strip().lower()
    if normalized not in {"bash", "zsh", "fish"}:
        raise ValueError("Unsupported shell. Expected one of: bash, zsh, fish.")
    return cast("Literal['bash', 'zsh', 'fish']", normalized)


@completion_app.command(name="bash")
def completion_bash() -> None:
    _emit_completion("bash")


@completion_app.command(name="zsh")
def completion_zsh() -> None:
    _emit_completion("zsh")


@completion_app.command(name="fish")
def completion_fish() -> None:
    _emit_completion("fish")


@completion_app.command(name="install")
def completion_install(
    shell: Annotated[str, Parameter(name="--shell")] = "bash",
    output: Annotated[str | None, Parameter(name="--output")] = None,
    add_to_startup: Annotated[bool, Parameter(name="--add-to-startup")] = False,
) -> None:
    normalized_shell = _normalize_completion_shell(shell)
    destination = app.install_completion(
        shell=normalized_shell,
        output=Path(output).expanduser() if output is not None else None,
        add_to_startup=add_to_startup,
    )
    emit({"shell": normalized_shell, "path": destination.as_posix()})


@app.command(name="start")
def start_alias(
    passthrough: Annotated[tuple[str, ...], Parameter(allow_leading_hyphen=True)] = (),
) -> None:
    """Alias for workspace start."""

    workspace_app(["start", *passthrough])


@app.command(name="list")
def list_alias() -> None:
    """Alias for run list."""

    run_app(["list"])


@app.command(name="show")
def show_alias(run_id: str = "r1") -> None:
    """Alias for run show."""

    run_app(["show", run_id])


@app.command(name="wait")
def wait_alias(run_id: str = "r1") -> None:
    """Alias for run wait."""

    run_app(["wait", run_id])


@app.command(name="doctor")
def doctor_alias() -> None:
    """Alias for diag doctor."""

    diag_app(["doctor"])


_REGISTERED_CLI_COMMANDS: set[str] = set()
_REGISTERED_CLI_DESCRIPTIONS: dict[str, str] = {}


def _register_group_commands() -> None:
    modules = (
        register_workspace_commands(workspace_app, emit),
        register_run_commands(run_app, emit),
        register_skills_commands(skills_app, emit),
        register_models_commands(models_app, emit),
        register_context_commands(context_app, emit),
        register_diag_commands(diag_app, emit),
        register_migrate_commands(migrate_app, emit),
    )
    for commands, descriptions in modules:
        _REGISTERED_CLI_COMMANDS.update(commands)
        _REGISTERED_CLI_DESCRIPTIONS.update(descriptions)


def get_registered_cli_commands() -> set[str]:
    """Expose CLI operation command names for parity tests."""

    return set(_REGISTERED_CLI_COMMANDS)


def get_registered_cli_descriptions() -> dict[str, str]:
    """Expose CLI descriptions for parity tests."""

    return dict(_REGISTERED_CLI_DESCRIPTIONS)


def main(argv: Sequence[str] | None = None) -> None:
    """CLI entry point used by `meridian` and `python -m meridian`."""

    args = list(sys.argv[1:] if argv is None else argv)
    with suppress(Exception):
        # Cleanup is best-effort and should never block CLI usage.
        cleanup_orphaned_locks(resolve_repo_root())
    cleaned_args, options = _extract_global_options(args)

    token = _GLOBAL_OPTIONS.set(options)
    try:
        app(cleaned_args)
    finally:
        _GLOBAL_OPTIONS.reset(token)


_register_group_commands()
register_export_commands(export_app, emit)
