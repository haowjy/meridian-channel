"""Path resolution helpers for repository-scoped config files."""

from __future__ import annotations

import os
from pathlib import Path

from meridian.lib.config.settings import SearchPathConfig
from meridian.lib.state.db import resolve_state_paths


def bundled_agents_root() -> Path | None:
    """Return the path to meridian's bundled .agents/ directory, when available."""

    import importlib.resources

    try:
        return Path(str(importlib.resources.files("meridian.resources") / ".agents"))
    except Exception:
        return None


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
    candidate = cwd
    while True:
        if (candidate / ".agents" / "skills").is_dir():
            return candidate

        git_marker = candidate / ".git"
        # A .git entry (file for worktree/submodule, directory for standalone
        # repo) marks a repo boundary.
        if git_marker.exists():
            return candidate

        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent

    return cwd


def resolve_search_paths(config: SearchPathConfig, repo_root: Path) -> list[Path]:
    """Resolve configured search paths, returning existing local then global directories."""

    return resolve_path_list(config.agents, config.global_agents, repo_root)


def resolve_path_list(
    local_paths: tuple[str, ...],
    global_paths: tuple[str, ...],
    repo_root: Path,
) -> list[Path]:
    """Resolve configured local + global paths into existing absolute directories."""

    resolved: list[Path] = []
    seen: set[Path] = set()
    for raw_path in (*local_paths, *global_paths):
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            candidate = repo_root / candidate
        absolute = candidate.resolve()
        if not absolute.is_dir() or absolute in seen:
            continue
        seen.add(absolute)
        resolved.append(absolute)
    return resolved


def default_index_db_path(repo_root: Path) -> Path:
    """Return default SQLite index path shared across meridian state."""

    return resolve_state_paths(repo_root).db_path
