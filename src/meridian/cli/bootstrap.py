"""Bootstrap helpers for meridian CLI startup behavior."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager

_TOP_LEVEL_VALUE_FLAGS = frozenset(
    {
        "--format",
        "--config",
        "--continue",
        "--fork",
        "--model",
        "-m",
        "--harness",
        "--agent",
        "-a",
        "--work",
        "--autocompact",
        "--effort",
        "--sandbox",
        "--approval",
        "--timeout",
    }
)
_TOP_LEVEL_BOOL_FLAGS = frozenset(
    {
        "--help",
        "-h",
        "--version",
        "--json",
        "--no-json",
        "--yes",
        "--no-yes",
        "--no-input",
        "--no-no-input",
        "--human",
        "--yolo",
        "--no-yolo",
        "--dry-run",
        "--no-dry-run",
    }
)


def _first_positional_token_with_index(argv: Sequence[str]) -> tuple[int, str] | None:
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--":
            return None
        if not token.startswith("-"):
            return index, token
        if "=" in token:
            index += 1
            continue
        if token in _TOP_LEVEL_BOOL_FLAGS:
            index += 1
            continue
        if token in _TOP_LEVEL_VALUE_FLAGS:
            index += 2
            continue
        if index + 1 < len(argv) and not argv[index + 1].startswith("-"):
            index += 2
            continue
        index += 1
    return None


def _first_positional_token(argv: Sequence[str]) -> str | None:
    resolved = _first_positional_token_with_index(argv)
    if resolved is None:
        return None
    _, token = resolved
    return token


def _first_subcommand_token(argv: Sequence[str]) -> str | None:
    resolved = _first_positional_token_with_index(argv)
    if resolved is None:
        return None
    index, _ = resolved
    for token in argv[index + 1 :]:
        if token == "--":
            return None
        if token.startswith("-"):
            continue
        return token
    return None


def validate_top_level_command(
    argv: Sequence[str],
    *,
    known_commands: set[str],
    global_harness: str | None = None,
) -> None:
    candidate = _first_positional_token(argv)
    if candidate is None:
        return
    if candidate in known_commands:
        return
    if global_harness is not None:
        return
    print(f"error: Unknown command: {candidate}", file=sys.stderr)
    raise SystemExit(1)


def is_root_help_request(argv: Sequence[str]) -> bool:
    if not any(token in {"--help", "-h"} for token in argv):
        return False
    return _first_positional_token(argv) is None


def should_startup_bootstrap(argv: Sequence[str]) -> bool:
    if any(token in {"--help", "-h", "--version"} for token in argv):
        return False
    top_level = _first_positional_token(argv)
    if top_level is None:
        return True
    if top_level in {"context", "session", "completion", "doctor"}:
        return False
    subcommand = _first_subcommand_token(argv)
    if top_level == "models" and subcommand in {None, "list", "show"}:
        return False
    if top_level == "config" and subcommand in {"show", "get"}:
        return False
    if top_level == "work" and subcommand in {None, "list", "show", "sessions", "current"}:
        return False
    return not (
        top_level == "spawn"
        and subcommand in {"list", "show", "stats", "wait", "files", "log", "report"}
    )


def maybe_bootstrap_runtime_state(argv: Sequence[str], *, agent_mode: bool) -> None:
    if agent_mode or not should_startup_bootstrap(argv):
        return
    try:
        from meridian.lib.config.settings import resolve_project_root
        from meridian.lib.ops.config import ensure_runtime_state_bootstrap_sync

        repo_root = resolve_project_root()
        ensure_runtime_state_bootstrap_sync(repo_root)
    except Exception:
        pass


@contextmanager
def temporary_config_env(config_file: str | None) -> Iterator[None]:
    if config_file is None:
        yield
        return

    prior_user_config = os.environ.get("MERIDIAN_CONFIG")
    os.environ["MERIDIAN_CONFIG"] = config_file
    try:
        yield
    finally:
        if prior_user_config is None:
            os.environ.pop("MERIDIAN_CONFIG", None)
        else:
            os.environ["MERIDIAN_CONFIG"] = prior_user_config
