"""Path resolution helpers for repository-scoped config files."""

from __future__ import annotations

import os
from pathlib import Path


def resolve_repo_root(explicit: Path | None = None) -> Path:
    """Resolve repository root that owns `.agents/skills/`.

    Precedence:
    1. Explicit function argument.
    2. `MERIDIAN_REPO_ROOT` environment variable.
    3. Current directory / ancestors containing `.agents/skills/`.
    4. Current working directory.
    """

    if explicit is not None:
        return explicit.expanduser().resolve()

    env_root = os.getenv("MERIDIAN_REPO_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / ".agents" / "skills").is_dir():
            return candidate
    return cwd


def canonical_skills_dir(repo_root: Path) -> Path:
    """Return canonical skill directory for this repository."""

    return repo_root / ".agents" / "skills"


def canonical_agents_dir(repo_root: Path) -> Path:
    """Return canonical agent-profile directory for this repository."""

    return repo_root / ".agents" / "agents"


def default_index_db_path(repo_root: Path) -> Path:
    """Return default SQLite index path shared across meridian state."""

    return repo_root / ".meridian" / "index" / "runs.db"

