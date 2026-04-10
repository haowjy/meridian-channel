"""Shared Claude preflight helpers for subprocess and streaming launches."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import cast

import structlog

from meridian.lib.harness.claude import project_slug

logger = structlog.get_logger(__name__)


def ensure_claude_session_accessible(
    source_session_id: str,
    source_cwd: Path | None,
    child_cwd: Path,
) -> None:
    """Symlink a Claude session file into the child's project dir.

    Claude Code maps sessions to ~/.claude/projects/<encoded-cwd>/.
    When the child runs from a different CWD than where the session was
    created, it can't find the session. This creates a symlink so both
    paths resolve.
    """

    if source_cwd is None:
        return
    if source_cwd.resolve() == child_cwd.resolve():
        return

    # Validate session ID to prevent path traversal.
    safe_session_id = Path(source_session_id).name
    if (
        safe_session_id != source_session_id
        or "/" in source_session_id
        or ".." in source_session_id
    ):
        return

    claude_projects = Path.home() / ".claude" / "projects"
    source_slug = project_slug(source_cwd)
    child_slug = project_slug(child_cwd)

    source_file = claude_projects / source_slug / f"{safe_session_id}.jsonl"
    if not source_file.exists():
        return

    child_project = claude_projects / child_slug
    child_project.mkdir(parents=True, exist_ok=True)
    target_file = child_project / f"{safe_session_id}.jsonl"
    try:
        os.symlink(source_file, target_file)
    except FileExistsError:
        # Verify existing entry points to the correct source.
        try:
            if target_file.resolve() != source_file.resolve():
                target_file.unlink()
                os.symlink(source_file, target_file)
        except OSError:
            pass  # Best effort.


def dedupe_nonempty(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for raw_value in values:
        value = raw_value.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def split_csv_entries(value: str) -> list[str]:
    return [entry.strip() for entry in value.split(",") if entry.strip()]


def read_parent_claude_permissions(execution_cwd: Path) -> tuple[list[str], list[str]]:
    additional_directories: list[str] = []
    allowed_tools: list[str] = []

    settings_dir = execution_cwd / ".claude"
    settings_files = (
        settings_dir / "settings.json",
        settings_dir / "settings.local.json",
    )

    for settings_path in settings_files:
        if not settings_path.exists():
            continue

        try:
            raw_payload = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning(
                "Failed to parse parent Claude settings while forwarding child permissions",
                path=str(settings_path),
            )
            continue

        if not isinstance(raw_payload, dict):
            continue
        payload = cast("dict[str, object]", raw_payload)
        raw_permissions = payload.get("permissions")
        if not isinstance(raw_permissions, dict):
            continue
        permissions = cast("dict[str, object]", raw_permissions)

        raw_additional_directories = permissions.get("additionalDirectories")
        if isinstance(raw_additional_directories, list):
            for directory in cast("list[object]", raw_additional_directories):
                if isinstance(directory, str):
                    additional_directories.append(directory)

        raw_allowed_tools = permissions.get("allow")
        if isinstance(raw_allowed_tools, list):
            for tool in cast("list[object]", raw_allowed_tools):
                if isinstance(tool, str):
                    allowed_tools.append(tool)

    return dedupe_nonempty(additional_directories), dedupe_nonempty(allowed_tools)


def merge_allowed_tools_flag(
    command: tuple[str, ...], additional_allowed_tools: list[str]
) -> tuple[str, ...]:
    if not additional_allowed_tools:
        return command

    existing_allowed_tools: list[str] = []
    merged_command: list[str] = []
    index = 0

    while index < len(command):
        arg = command[index]
        if arg == "--allowedTools":
            if index + 1 < len(command):
                existing_allowed_tools.extend(split_csv_entries(command[index + 1]))
                index += 2
                continue
            index += 1
            continue
        if arg.startswith("--allowedTools="):
            existing_allowed_tools.extend(split_csv_entries(arg.split("=", 1)[1]))
            index += 1
            continue
        merged_command.append(arg)
        index += 1

    combined_allowed_tools = dedupe_nonempty(existing_allowed_tools + additional_allowed_tools)
    if not combined_allowed_tools:
        return tuple(merged_command)
    merged_command.extend(("--allowedTools", ",".join(combined_allowed_tools)))
    return tuple(merged_command)


__all__ = [
    "ensure_claude_session_accessible",
    "merge_allowed_tools_flag",
    "read_parent_claude_permissions",
]
