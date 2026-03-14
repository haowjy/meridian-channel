"""Install-state provenance lookups for resolved runtime assets."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from meridian.lib.install.lock import InstallLock, read_lock
from meridian.lib.state.paths import resolve_state_paths


class RuntimeAssetProvenance(BaseModel):
    """Resolved source ownership for runtime-selected assets."""

    model_config = ConfigDict(frozen=True)

    agent_source: str | None = None
    skill_sources: dict[str, str] = Field(default_factory=dict)


def resolve_runtime_asset_provenance(
    *,
    repo_root: Path,
    agent_path: str = "",
    skill_paths: tuple[str, ...] = (),
) -> RuntimeAssetProvenance:
    """Resolve managed source ownership for installed runtime assets."""

    lock = read_lock(resolve_state_paths(repo_root).agents_lock_path)
    return RuntimeAssetProvenance(
        agent_source=_source_name_for_path(lock, repo_root=repo_root, asset_path=agent_path),
        skill_sources={
            _skill_name_from_path(path): source_name
            for path in skill_paths
            if (source_name := _source_name_for_path(lock, repo_root=repo_root, asset_path=path))
            is not None
        },
    )


def _source_name_for_path(
    lock: InstallLock,
    *,
    repo_root: Path,
    asset_path: str,
) -> str | None:
    normalized = _normalized_relative_path(repo_root=repo_root, asset_path=asset_path)
    if normalized is None:
        return None

    for item in lock.items.values():
        if item.destination_path == normalized:
            return item.source_name
        if normalized == f"{item.destination_path}/SKILL.md":
            return item.source_name
    return None


def _normalized_relative_path(*, repo_root: Path, asset_path: str) -> str | None:
    raw = asset_path.strip()
    if not raw:
        return None

    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = (repo_root / candidate).resolve()
    else:
        candidate = candidate.resolve()

    try:
        return candidate.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return None


def _skill_name_from_path(raw_path: str) -> str:
    path = Path(raw_path).expanduser().resolve()
    if path.name == "SKILL.md":
        return path.parent.name
    return path.stem
