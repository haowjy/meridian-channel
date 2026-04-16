"""Runtime context derived from MERIDIAN_* environment variables."""

from contextlib import suppress
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict

from meridian.lib.core.types import SpawnId
from meridian.lib.state.paths import resolve_work_scratch_dir

_ALLOWED_MERIDIAN_KEYS: frozenset[str] = frozenset(
    {
        "MERIDIAN_REPO_ROOT",
        "MERIDIAN_STATE_ROOT",
        "MERIDIAN_DEPTH",
        "MERIDIAN_CHAT_ID",
        "MERIDIAN_FS_DIR",
        "MERIDIAN_WORK_ID",
        "MERIDIAN_WORK_DIR",
    }
)


class RuntimeContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    spawn_id: SpawnId | None = None
    depth: int = 0
    repo_root: Path | None = None
    state_root: Path | None = None
    chat_id: str = ""
    fs_dir: Path | None = None
    work_id: str | None = None
    work_dir: Path | None = None

    @classmethod
    def from_environment(cls) -> Self:
        """Build context from MERIDIAN_* environment variables."""

        import os

        spawn_id_raw = os.getenv("MERIDIAN_SPAWN_ID", "").strip()
        depth_raw = os.getenv("MERIDIAN_DEPTH", "0").strip()
        repo_root_raw = os.getenv("MERIDIAN_REPO_ROOT", "").strip()
        state_root_raw = os.getenv("MERIDIAN_STATE_ROOT", "").strip()
        chat_id_raw = os.getenv("MERIDIAN_CHAT_ID", "").strip()
        fs_dir_raw = os.getenv("MERIDIAN_FS_DIR", "").strip()
        work_id_raw = os.getenv("MERIDIAN_WORK_ID", "").strip()
        work_dir_raw = os.getenv("MERIDIAN_WORK_DIR", "").strip()

        depth = 0
        with suppress(ValueError, TypeError):
            depth = max(0, int(depth_raw))

        return cls(
            spawn_id=SpawnId(spawn_id_raw) if spawn_id_raw else None,
            depth=depth,
            repo_root=Path(repo_root_raw) if repo_root_raw else None,
            state_root=Path(state_root_raw) if state_root_raw else None,
            chat_id=chat_id_raw,
            fs_dir=Path(fs_dir_raw) if fs_dir_raw else None,
            work_id=work_id_raw or None,
            work_dir=Path(work_dir_raw) if work_dir_raw else None,
        )

    def to_env_overrides(self) -> dict[str, str]:
        """Produce MERIDIAN_* env overrides for child processes."""

        overrides: dict[str, str] = {"MERIDIAN_DEPTH": str(self.depth)}
        if self.spawn_id is not None:
            overrides["MERIDIAN_SPAWN_ID"] = str(self.spawn_id)
        if self.repo_root is not None:
            overrides["MERIDIAN_REPO_ROOT"] = self.repo_root.as_posix()
        if self.state_root is not None:
            overrides["MERIDIAN_STATE_ROOT"] = self.state_root.as_posix()
        if self.chat_id:
            overrides["MERIDIAN_CHAT_ID"] = self.chat_id
        if self.fs_dir is not None:
            overrides["MERIDIAN_FS_DIR"] = self.fs_dir.as_posix()
        if self.work_id:
            overrides["MERIDIAN_WORK_ID"] = self.work_id
            if self.work_dir is not None:
                overrides["MERIDIAN_WORK_DIR"] = self.work_dir.as_posix()
            elif self.state_root is not None:
                overrides["MERIDIAN_WORK_DIR"] = resolve_work_scratch_dir(
                    self.state_root,
                    self.work_id,
                ).as_posix()
        return overrides

    def with_work_id(self, work_id: str | None) -> Self:
        normalized = (work_id or "").strip()
        if not normalized:
            return self
        next_work_dir: Path | None = self.work_dir
        if self.state_root is not None:
            next_work_dir = resolve_work_scratch_dir(self.state_root, normalized)
        return self.model_copy(update={"work_id": normalized, "work_dir": next_work_dir})

    def child_context(self) -> dict[str, str]:
        """Produce child MERIDIAN_* env overrides for spawned subprocesses."""

        if self.repo_root is None or self.state_root is None:
            raise RuntimeError("RuntimeContext.child_context requires repo_root and state_root")

        overrides: dict[str, str] = {
            "MERIDIAN_REPO_ROOT": self.repo_root.as_posix(),
            "MERIDIAN_STATE_ROOT": self.state_root.as_posix(),
            "MERIDIAN_DEPTH": str(self.depth + 1),
        }
        if self.chat_id:
            overrides["MERIDIAN_CHAT_ID"] = self.chat_id
        if self.fs_dir is not None:
            overrides["MERIDIAN_FS_DIR"] = self.fs_dir.as_posix()
        if self.work_id:
            overrides["MERIDIAN_WORK_ID"] = self.work_id
            if self.work_dir is not None:
                overrides["MERIDIAN_WORK_DIR"] = self.work_dir.as_posix()
            else:
                overrides["MERIDIAN_WORK_DIR"] = resolve_work_scratch_dir(
                    self.state_root,
                    self.work_id,
                ).as_posix()

        if not set(overrides).issubset(_ALLOWED_MERIDIAN_KEYS):
            missing = sorted(set(overrides) - _ALLOWED_MERIDIAN_KEYS)
            raise RuntimeError(f"RuntimeContext.child_context drifted keys: {missing}")
        return overrides
