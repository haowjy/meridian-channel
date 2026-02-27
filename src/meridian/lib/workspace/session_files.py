"""Session-scoped workspace file helpers."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from meridian.lib.state.db import resolve_state_paths

_SESSION_ENV_VAR = "MERIDIAN_SESSION"


def resolve_workspace_session_id(session_id: str | None = None) -> str | None:
    """Resolve session ID from explicit input or MERIDIAN_SESSION."""

    resolved = session_id.strip() if session_id is not None else ""
    if not resolved:
        resolved = os.getenv(_SESSION_ENV_VAR, "").strip()
    if not resolved:
        return None
    return resolved


def generate_workspace_session_id() -> str:
    """Generate a compact random session ID."""

    return secrets.token_hex(4)


def normalize_workspace_file_reference(name: str) -> str:
    """Normalize `@name`/`name` into a flat file stem."""

    normalized = name.strip()
    if normalized.startswith("@"):
        normalized = normalized[1:].strip()
    if not normalized:
        raise ValueError("Workspace file name must not be empty.")
    if "/" in normalized or "\\" in normalized:
        raise ValueError("Workspace file names use a flat namespace; '/' is not allowed.")
    if normalized in {".", ".."}:
        raise ValueError("Workspace file name must not be '.' or '..'.")
    return normalized


def workspace_session_files_dir(repo_root: Path, session_id: str) -> Path:
    """Return session file directory under Meridian state root."""

    normalized = session_id.strip()
    if not normalized:
        raise ValueError("Session ID is required.")
    return resolve_state_paths(repo_root).root_dir / "sessions" / normalized


def workspace_session_file_path(repo_root: Path, session_id: str, name: str) -> Path:
    """Resolve one session file path from session ID and logical name."""

    normalized_name = normalize_workspace_file_reference(name)
    file_name = normalized_name if normalized_name.endswith(".md") else f"{normalized_name}.md"
    return workspace_session_files_dir(repo_root, session_id) / file_name


def display_workspace_file_name(path: Path) -> str:
    """Render canonical display name with @ prefix."""

    if path.suffix == ".md":
        return f"@{path.stem}"
    return f"@{path.name}"
