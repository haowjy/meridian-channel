"""Cyclopts CLI entry point for meridian."""

from __future__ import annotations

import logging
import os
import sys
from contextvars import ContextVar
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal, cast

from cyclopts import App, Parameter

from meridian import __version__
from meridian.cli.config_cmd import register_config_commands
from meridian.cli.doctor_cmd import register_doctor_command
from meridian.cli.models_cmd import register_models_commands
from meridian.cli.output import OutputConfig, normalize_output_format
from meridian.cli.output import emit as emit_output
from meridian.cli.run import register_run_commands
from meridian.cli.skills_cmd import register_skills_commands
from meridian.cli.space import register_space_commands
from meridian.lib.config._paths import resolve_repo_root
from meridian.lib.ops.space import SpaceActionOutput
from meridian.lib.space import space_file
from meridian.lib.space.launch import SpaceLaunchRequest, cleanup_orphaned_locks, launch_primary
from meridian.lib.space.summary import generate_space_summary
from meridian.lib.types import SpaceId
from meridian.server.main import run_server

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

_AGENT_ROOT_HELP = """Usage: meridian COMMAND [ARGS]

Meridian orchestrator CLI

Commands:
  doctor: Run diagnostics checks.
  models: Model catalog commands
  run: Run management commands
  skills: Skills catalog commands
  --help, -h: Display this message and exit.
  --version: Display application version.

Parameters:
  JSON, --json, --no-json: Emit command output as JSON. [default: False]
  FORMAT, --format: Set output format: text, json, or porcelain.
  PORCELAIN, --porcelain, --no-porcelain: Emit stable tab-separated key/value
output. [default: False]
  YES, --yes, --no-yes: Auto-approve prompts when supported. [default: False]
  NO-INPUT, --no-input, --no-no-input: Disable interactive prompts and fail if
input is needed. [default: False]
"""


@dataclass(frozen=True, slots=True)
class GlobalOptions:
    """Top-level options that apply to all commands."""

    output: OutputConfig
    yes: bool = False
    no_input: bool = False
    output_explicit: bool = False


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
    output_explicit = False
    cleaned: list[str] = []

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--json":
            json_mode = True
            output_explicit = True
            i += 1
            continue
        if arg == "--no-json":
            output_explicit = True
            i += 1
            continue
        if arg == "--porcelain":
            porcelain_mode = True
            output_explicit = True
            i += 1
            continue
        if arg == "--no-porcelain":
            output_explicit = True
            i += 1
            continue
        if arg == "--format":
            if i + 1 >= len(argv):
                raise SystemExit("--format requires a value")
            output_format = argv[i + 1]
            output_explicit = True
            i += 2
            continue
        if arg.startswith("--format="):
            output_format = arg.partition("=")[2]
            output_explicit = True
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
    )
    return cleaned, GlobalOptions(
        output=OutputConfig(format=resolved),
        yes=yes,
        no_input=no_input,
        output_explicit=output_explicit,
    )


def _extract_human_flag(argv: Sequence[str]) -> tuple[list[str], bool]:
    force_human = False
    cleaned: list[str] = []
    for arg in argv:
        if arg == "--human":
            force_human = True
            continue
        cleaned.append(arg)
    return cleaned, force_human


def _agent_mode_enabled() -> bool:
    return bool(os.getenv("MERIDIAN_SPACE_ID", "").strip())


app = App(
    name="meridian",
    help="Meridian orchestrator CLI",
    version=__version__,
    help_formatter="plain",
)
_COMMAND_TREE_APP = app


@app.default
def root(
    json_mode: Annotated[
        bool,
        Parameter(name="--json", help="Emit command output as JSON."),
    ] = False,
    output_format: Annotated[
        str | None,
        Parameter(name="--format", help="Set output format: text, json, or porcelain."),
    ] = None,
    porcelain: Annotated[
        bool,
        Parameter(name="--porcelain", help="Emit stable tab-separated key/value output."),
    ] = False,
    yes: Annotated[
        bool,
        Parameter(name="--yes", help="Auto-approve prompts when supported."),
    ] = False,
    no_input: Annotated[
        bool,
        Parameter(
            name="--no-input",
            help="Disable interactive prompts and fail if input is needed.",
        ),
    ] = False,
) -> None:
    """Meridian root command with global options."""

    resolved = normalize_output_format(
        requested=output_format,
        json_mode=json_mode,
        porcelain_mode=porcelain,
    )
    _GLOBAL_OPTIONS.set(
        GlobalOptions(output=OutputConfig(format=resolved), yes=yes, no_input=no_input)
    )
    app.help_print()


@app.command(name="serve")
def serve() -> None:
    """Start FastMCP server on stdio."""

    run_server()


space_app = App(name="space", help="Space lifecycle commands", help_formatter="plain")
run_app = App(name="run", help="Run management commands", help_formatter="plain")
skills_app = App(name="skills", help="Skills catalog commands", help_formatter="plain")
models_app = App(name="models", help="Model catalog commands", help_formatter="plain")
config_app = App(name="config", help="Repository config commands", help_formatter="plain")

completion_app = App(name="completion", help="Shell completion helpers", help_formatter="plain")


app.command(space_app, name="space")
app.command(run_app, name="run")
app.command(skills_app, name="skills")
app.command(models_app, name="models")
app.command(config_app, name="config")
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
    shell: Annotated[
        str,
        Parameter(name="--shell", help="Shell to generate completion for (bash, zsh, or fish)."),
    ] = "bash",
    output: Annotated[
        str | None,
        Parameter(name="--output", help="Optional file path where completion script is written."),
    ] = None,
    add_to_startup: Annotated[
        bool,
        Parameter(name="--add-to-startup", help="Append completion setup to shell startup files."),
    ] = False,
) -> None:
    normalized_shell = _normalize_completion_shell(shell)
    destination = app.install_completion(
        shell=normalized_shell,
        output=Path(output).expanduser() if output is not None else None,
        add_to_startup=add_to_startup,
    )
    emit({"shell": normalized_shell, "path": destination.as_posix()})


def _start_space_record(
    *,
    repo_root: Path,
    force_new: bool,
    explicit_space: str | None,
) -> space_file.SpaceRecord:
    if force_new and explicit_space is not None:
        raise ValueError("Cannot combine --new with --space.")

    if explicit_space is not None:
        record = space_file.get_space(repo_root, explicit_space)
        if record is None:
            raise ValueError(f"Space '{explicit_space}' not found")
        return record

    if force_new:
        return space_file.create_space(repo_root)

    spaces = space_file.list_spaces(repo_root)
    active = [record for record in spaces if record.status == "active"]
    if active:
        return max(active, key=lambda record: record.created_at)
    return space_file.create_space(repo_root)


def _summary_text(path: str) -> str:
    summary_path = Path(path)
    if not summary_path.is_file():
        return ""
    return summary_path.read_text(encoding="utf-8")


@app.command(name="start")
def start(
    new: Annotated[
        bool,
        Parameter(name="--new", help="Force create a new space before launch."),
    ] = False,
    space: Annotated[
        str | None,
        Parameter(name="--space", help="Use an explicit existing space id."),
    ] = None,
    continue_mode: Annotated[
        bool,
        Parameter(name="--continue", help="Continue mode (currently stubbed)."),
    ] = False,
    model: Annotated[
        str,
        Parameter(name="--model", help="Model id or alias for primary harness."),
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
    """Resolve/start a space and launch the primary harness."""

    if continue_mode:
        raise ValueError(
            "ERROR [NOT_IMPLEMENTED]: --continue is not wired yet. "
            "Next: use `meridian start` without --continue."
        )

    repo_root = resolve_repo_root()
    explicit_space = space.strip() if space is not None and space.strip() else None
    selected = _start_space_record(
        repo_root=repo_root,
        force_new=new,
        explicit_space=explicit_space,
    )
    summary_path = generate_space_summary(
        repo_root=repo_root,
        space_id=SpaceId(selected.id),
    )

    launch_result = launch_primary(
        repo_root=repo_root,
        request=SpaceLaunchRequest(
            space_id=SpaceId(selected.id),
            model=model,
            autocompact=autocompact,
            passthrough_args=harness_args,
            fresh=True,
            summary_text=_summary_text(summary_path.as_posix()),
            pinned_context="",
            dry_run=dry_run,
        ),
    )

    transitioned = space_file.update_space_status(
        repo_root,
        selected.id,
        launch_result.final_state,
    )
    emit(
        SpaceActionOutput(
            space_id=selected.id,
            state=transitioned.status,
            message=("Space launch dry-run." if dry_run else "Space session finished."),
            exit_code=launch_result.exit_code,
            command=launch_result.command,
            lock_path=launch_result.lock_path.as_posix(),
            summary_path=summary_path.as_posix(),
        )
    )


@app.command(name="init")
def init_alias() -> None:
    """Alias for config init."""

    config_app(["init"])


_REGISTERED_CLI_COMMANDS: set[str] = set()
_REGISTERED_CLI_DESCRIPTIONS: dict[str, str] = {}


def _register_group_commands() -> None:
    modules = (
        register_space_commands(space_app, emit),
        register_run_commands(run_app, emit),
        register_skills_commands(skills_app, emit),
        register_models_commands(models_app, emit),
        register_config_commands(config_app, emit),
        register_doctor_command(app, emit),
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


def _operation_error_message(exc: Exception) -> str:
    if isinstance(exc, KeyError) and exc.args:
        return str(exc.args[0])
    message = str(exc).strip()
    if message:
        return message
    return exc.__class__.__name__


def _first_positional_token(argv: Sequence[str]) -> str | None:
    for token in argv:
        if token == "--":
            return None
        if token.startswith("-"):
            continue
        return token
    return None


def _top_level_command_names() -> set[str]:
    return {
        name for name in _COMMAND_TREE_APP.resolved_commands() if not name.startswith("-")
    }


def _validate_top_level_command(argv: Sequence[str]) -> None:
    candidate = _first_positional_token(argv)
    if candidate is None:
        return
    if candidate in _top_level_command_names():
        return
    print(f"error: Unknown command: {candidate}", file=sys.stderr)
    raise SystemExit(1)


def _is_root_help_request(argv: Sequence[str]) -> bool:
    if not any(token in {"--help", "-h"} for token in argv):
        return False
    return _first_positional_token(argv) is None


def _print_agent_root_help() -> None:
    print(_AGENT_ROOT_HELP, end="")


def main(argv: Sequence[str] | None = None) -> None:
    """CLI entry point used by `meridian` and `python -m meridian`."""

    from meridian.lib.logging import configure_logging

    args = list(sys.argv[1:] if argv is None else argv)

    # Configure logging early so structlog warnings go to stderr, not stdout.
    json_mode = "--json" in args or "--format" in args
    verbose_count = args.count("--verbose") + args.count("-v")
    configure_logging(json_mode=json_mode, verbosity=verbose_count)

    try:
        # Cleanup is best-effort and should never block CLI usage.
        cleanup_orphaned_locks(resolve_repo_root())
    except Exception:
        logger.debug("orphaned lock cleanup failed", exc_info=True)

    args, force_human = _extract_human_flag(args)
    cleaned_args, options = _extract_global_options(args)

    agent_mode = _agent_mode_enabled() and not force_human
    if agent_mode and not options.output_explicit:
        options = replace(options, output=OutputConfig(format="json"))

    if agent_mode and (not cleaned_args or _is_root_help_request(cleaned_args)):
        _print_agent_root_help()
        return

    _validate_top_level_command(cleaned_args)

    token = _GLOBAL_OPTIONS.set(options)
    try:
        try:
            app(cleaned_args)
        except TimeoutError as exc:
            print(f"error: {_operation_error_message(exc)}", file=sys.stderr)
            raise SystemExit(124) from None
        except (KeyError, ValueError, FileNotFoundError, OSError) as exc:
            print(f"error: {_operation_error_message(exc)}", file=sys.stderr)
            raise SystemExit(1) from None
    finally:
        _GLOBAL_OPTIONS.reset(token)


_register_group_commands()
