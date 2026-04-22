"""Context path resolution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from meridian.lib.config.context_config import (
    ArbitraryContextConfig,
    ContextConfig,
    ContextSourceType,
)
from meridian.lib.state.user_paths import get_project_uuid
from meridian.plugin_api import resolve_clone_path


@dataclass(frozen=True)
class ResolvedContextPaths:
    """Resolved context paths after substitution."""

    work_root: Path
    work_archive: Path
    work_source: ContextSourceType
    kb_root: Path
    kb_source: ContextSourceType
    extra: dict[str, tuple[Path, ContextSourceType]]


def context_uses_project_placeholder(config: ContextConfig) -> bool:
    """Return whether any configured context path references ``{project}``."""

    if "{project}" in config.work.path:
        return True
    if "{project}" in config.work.archive:
        return True
    if "{project}" in config.kb.path:
        return True

    extras_raw = getattr(config, "__pydantic_extra__", None)
    extras = cast("dict[str, object]", extras_raw) if isinstance(extras_raw, dict) else {}
    for value in extras.values():
        parsed = (
            value
            if isinstance(value, ArbitraryContextConfig)
            else ArbitraryContextConfig.model_validate(value)
        )
        if "{project}" in parsed.path:
            return True
    return False


def _resolve_path(
    path_spec: str,
    project_root: Path,
    project_uuid: str | None,
    *,
    source: ContextSourceType = ContextSourceType.LOCAL,
    remote: str | None = None,
) -> Path:
    """Resolve one path spec with substitution and root rules.

    When source is GIT and remote is provided, resolves path relative to
    the auto-cloned repository location. The clone itself is handled lazily
    by git-autosync hooks, not here.
    """
    if project_uuid and "{project}" in path_spec:
        path_spec = path_spec.replace("{project}", project_uuid)

    # For git-backed contexts, resolve relative to the expected clone location
    if source == ContextSourceType.GIT and isinstance(remote, str) and remote.strip():
        clone_root = resolve_clone_path(remote.strip())
        return clone_root / path_spec

    candidate = Path(path_spec).expanduser()
    if candidate.is_absolute():
        return candidate
    return project_root / candidate


def resolve_context_paths(
    project_root: Path,
    config: ContextConfig,
    project_uuid: str | None = None,
) -> ResolvedContextPaths:
    """Resolve context paths from config."""

    if project_uuid is None:
        project_uuid = get_project_uuid(project_root / ".meridian")

    work_root = _resolve_path(
        config.work.path,
        project_root,
        project_uuid,
        source=config.work.source,
        remote=config.work.remote,
    )
    work_archive = _resolve_path(
        config.work.archive,
        project_root,
        project_uuid,
        source=config.work.source,
        remote=config.work.remote,
    )
    kb_root = _resolve_path(
        config.kb.path,
        project_root,
        project_uuid,
        source=config.kb.source,
        remote=config.kb.remote,
    )

    extra: dict[str, tuple[Path, ContextSourceType]] = {}
    extras_raw = getattr(config, "__pydantic_extra__", None)
    extras = cast("dict[str, object]", extras_raw) if isinstance(extras_raw, dict) else {}
    for name, value in extras.items():
        parsed = (
            value
            if isinstance(value, ArbitraryContextConfig)
            else ArbitraryContextConfig.model_validate(value)
        )
        extra[name] = (
            _resolve_path(
                parsed.path,
                project_root,
                project_uuid,
                source=parsed.source,
                remote=parsed.remote,
            ),
            parsed.source,
        )

    return ResolvedContextPaths(
        work_root=work_root,
        work_archive=work_archive,
        work_source=config.work.source,
        kb_root=kb_root,
        kb_source=config.kb.source,
        extra=extra,
    )
