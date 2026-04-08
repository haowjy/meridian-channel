"""Shared Mars helpers used by Meridian operations and CLI wrappers."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict


class UpgradeAvailability(BaseModel):
    """Update availability summary for pinned Mars dependencies."""

    model_config = ConfigDict(frozen=True)

    count: int
    names: tuple[str, ...] = ()


def resolve_mars_executable() -> str | None:
    """Prefer the Mars binary from this install environment over PATH."""

    # Keep the wrapper path intact: uv tool scripts point at a symlinked Python
    # binary, and resolving it jumps out of the tool environment where sibling
    # scripts (including `mars`) live.
    scripts_dir = Path(sys.executable).parent
    for name in ("mars", "mars.exe"):
        candidate = scripts_dir / name
        if candidate.is_file():
            return str(candidate)
    return shutil.which("mars")


def _is_head_constraint(value: object) -> bool:
    if not isinstance(value, str):
        return False
    return value.strip().upper() == "HEAD"


def check_upgrade_availability(repo_root: Path | None = None) -> UpgradeAvailability | None:
    """Return updateable dependency names from ``mars outdated --json``.

    Returns ``None`` when the check cannot be completed (missing binary, command
    failure, malformed JSON, timeout). HEAD-constrained rows are ignored because
    they track moving refs and would produce noisy perpetual updates.
    """

    executable = resolve_mars_executable()
    if executable is None:
        return None

    command = [executable, "outdated", "--json"]
    if repo_root is not None:
        command.extend(["--root", repo_root.as_posix()])

    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None

    try:
        payload = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return None

    if not isinstance(payload, list):
        return None

    names: list[str] = []
    seen: set[str] = set()
    for row_obj in cast("list[object]", payload):
        if not isinstance(row_obj, dict):
            continue
        row = cast("dict[str, object]", row_obj)
        source = row.get("source")
        if not isinstance(source, str):
            continue
        normalized_source = source.strip()
        if not normalized_source:
            continue
        if _is_head_constraint(row.get("constraint")):
            continue

        locked = row.get("locked")
        updateable = row.get("updateable")
        if not isinstance(locked, str) or not isinstance(updateable, str):
            continue
        if locked.strip() == updateable.strip():
            continue
        if normalized_source in seen:
            continue
        seen.add(normalized_source)
        names.append(normalized_source)

    return UpgradeAvailability(count=len(names), names=tuple(names))


def format_upgrade_hint_lines(availability: UpgradeAvailability) -> tuple[str, str]:
    """Render the 2-line post-sync upgrade hint."""

    noun = "update" if availability.count == 1 else "updates"
    deps = ", ".join(availability.names)
    line1 = f"hint: {availability.count} {noun} available ({deps})."
    line2 = (
        "      Run `meridian mars outdated` to see details, or "
        "`meridian mars upgrade` to apply."
    )
    return line1, line2


__all__ = [
    "UpgradeAvailability",
    "check_upgrade_availability",
    "format_upgrade_hint_lines",
    "resolve_mars_executable",
]
