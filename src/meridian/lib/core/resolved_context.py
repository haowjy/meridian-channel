"""Authoritative runtime-context resolution from ``MERIDIAN_*`` inputs.

This module defines the canonical environment-to-context translation used by
launch, ops, and child-environment composition paths.
"""

from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Self

from meridian.lib.config.context_config import ContextConfig
from meridian.lib.context.resolver import resolve_context_paths
from meridian.lib.core.types import SpawnId
from meridian.lib.state import paths as state_paths
from meridian.lib.state import session_store


class ContextBackend(Protocol):
    """Backend interface for the authoritative context resolution workflow."""

    def get_session_active_work_id(self, state_root: Path, chat_id: str) -> str | None:
        """Look up the active work ID for a session."""
        ...

    def resolve_work_scratch_dir(self, state_root: Path, work_id: str) -> Path:
        """Resolve the scratch directory for a work item."""
        ...


class LocalFilesystemBackend:
    """Default context backend backed by local state modules."""

    def get_session_active_work_id(self, state_root: Path, chat_id: str) -> str | None:
        return session_store.get_session_active_work_id(state_root, chat_id)

    def resolve_work_scratch_dir(self, state_root: Path, work_id: str) -> Path:
        return state_paths.resolve_work_scratch_dir(state_root, work_id)


@dataclass(frozen=True)
class ResolvedContext:
    """Canonical immutable runtime context resolved from ``MERIDIAN_*`` inputs."""

    spawn_id: SpawnId | None = None
    depth: int = 0
    repo_root: Path | None = None
    state_root: Path | None = None
    chat_id: str = ""
    work_id: str | None = None
    work_dir: Path | None = None
    kb_dir: Path | None = None
    context_dirs: tuple[tuple[str, Path], ...] = ()

    @classmethod
    def from_environment(
        cls,
        *,
        explicit_work_id: str | None = None,
        backend: ContextBackend | None = None,
        context_config: ContextConfig | None = None,
    ) -> Self:
        """Resolve and freeze canonical runtime context from ``MERIDIAN_*`` values."""

        import os

        backend_impl = backend or LocalFilesystemBackend()

        spawn_id_raw = os.getenv("MERIDIAN_SPAWN_ID", "").strip()
        depth_raw = os.getenv("MERIDIAN_DEPTH", "0").strip()
        repo_root_raw = os.getenv("MERIDIAN_REPO_ROOT", "").strip()
        state_root_raw = os.getenv("MERIDIAN_STATE_ROOT", "").strip()
        chat_id_raw = os.getenv("MERIDIAN_CHAT_ID", "").strip()
        work_id_raw = os.getenv("MERIDIAN_WORK_ID", "").strip()
        explicit_work_id_raw = (explicit_work_id or "").strip()

        depth = 0
        with suppress(ValueError, TypeError):
            depth = max(0, int(depth_raw))

        repo_root = Path(repo_root_raw) if repo_root_raw else None
        state_root = Path(state_root_raw) if state_root_raw else None

        # Authoritative work-ID precedence:
        # explicit override > MERIDIAN_WORK_ID > session active work lookup.
        work_id: str | None = None
        if explicit_work_id_raw:
            work_id = explicit_work_id_raw
        elif work_id_raw:
            work_id = work_id_raw
        elif state_root is not None and chat_id_raw:
            work_id = backend_impl.get_session_active_work_id(state_root, chat_id_raw)

        repo_state_paths = (
            state_paths.resolve_repo_state_paths_from_context(
                repo_root,
                context_config=context_config,
            )
            if repo_root is not None
            else None
        )

        work_dir: Path | None = None
        if work_id:
            # Repo-scoped state paths take precedence when repo_root is known.
            if repo_state_paths is not None:
                work_dir = repo_state_paths.work_dir / work_id
            elif state_root is not None:
                work_dir = backend_impl.resolve_work_scratch_dir(state_root, work_id)

        kb_dir = repo_state_paths.kb_dir if repo_state_paths is not None else None

        resolved_config = context_config
        if resolved_config is None and repo_root is not None:
            resolved_config = state_paths.load_context_config(repo_root)

        context_dirs: tuple[tuple[str, Path], ...] = ()
        if repo_root is not None and resolved_config is not None:
            resolved_context_paths = resolve_context_paths(repo_root, resolved_config)
            context_dirs = tuple(
                sorted((name, path) for name, (path, _) in resolved_context_paths.extra.items())
            )

        return cls(
            spawn_id=SpawnId(spawn_id_raw) if spawn_id_raw else None,
            depth=depth,
            repo_root=repo_root,
            state_root=state_root,
            chat_id=chat_id_raw,
            work_id=work_id,
            work_dir=work_dir,
            kb_dir=kb_dir,
            context_dirs=context_dirs,
        )

    def child_env_overrides(self, *, increment_depth: bool = True) -> dict[str, str]:
        """Produce `MERIDIAN_*` env overrides for child processes."""

        next_depth = self.depth + 1 if increment_depth else self.depth
        overrides: dict[str, str] = {"MERIDIAN_DEPTH": str(next_depth)}
        if self.spawn_id is not None:
            overrides["MERIDIAN_SPAWN_ID"] = str(self.spawn_id)
        if self.repo_root is not None:
            overrides["MERIDIAN_REPO_ROOT"] = self.repo_root.as_posix()
        if self.state_root is not None:
            overrides["MERIDIAN_STATE_ROOT"] = self.state_root.as_posix()
        if self.chat_id:
            overrides["MERIDIAN_CHAT_ID"] = self.chat_id
        if self.work_id:
            overrides["MERIDIAN_WORK_ID"] = self.work_id
        if self.work_dir is not None:
            overrides["MERIDIAN_WORK_DIR"] = self.work_dir.as_posix()
        if self.kb_dir is not None:
            kb_value = self.kb_dir.as_posix()
            overrides["MERIDIAN_KB_DIR"] = kb_value
            # Deprecated alias: keep while callers migrate to MERIDIAN_KB_DIR.
            overrides["MERIDIAN_FS_DIR"] = kb_value
        for context_name, context_dir in self.context_dirs:
            env_name = "".join(
                character if character.isalnum() else "_"
                for character in context_name.upper()
            ).strip("_")
            if not env_name:
                continue
            overrides[f"MERIDIAN_CONTEXT_{env_name}_DIR"] = context_dir.as_posix()
        return overrides

    @property
    def fs_dir(self) -> Path | None:
        """Deprecated compatibility alias for ``kb_dir``."""

        return self.kb_dir
