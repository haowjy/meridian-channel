"""Unit tests for immutable resolved runtime context construction."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from meridian.lib.core.resolved_context import ContextBackend, ResolvedContext

_MERIDIAN_ENV_KEYS = (
    "MERIDIAN_SPAWN_ID",
    "MERIDIAN_DEPTH",
    "MERIDIAN_REPO_ROOT",
    "MERIDIAN_STATE_ROOT",
    "MERIDIAN_CHAT_ID",
    "MERIDIAN_WORK_ID",
    "MERIDIAN_WORK_DIR",
    "MERIDIAN_FS_DIR",
)


class FakeBackend(ContextBackend):
    def __init__(
        self,
        *,
        session_active_work_id: str | None = None,
        work_dir_suffix: str = "resolved",
    ) -> None:
        self.session_active_work_id = session_active_work_id
        self.work_dir_suffix = work_dir_suffix
        self.session_lookup_calls: list[tuple[Path, str]] = []
        self.work_dir_calls: list[tuple[Path, str]] = []

    def get_session_active_work_id(self, state_root: Path, chat_id: str) -> str | None:
        self.session_lookup_calls.append((state_root, chat_id))
        return self.session_active_work_id

    def resolve_work_scratch_dir(self, state_root: Path, work_id: str) -> Path:
        self.work_dir_calls.append((state_root, work_id))
        return state_root / "work" / self.work_dir_suffix / work_id


def _clear_meridian_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _MERIDIAN_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_from_environment_without_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_meridian_env(monkeypatch)
    backend = FakeBackend()

    resolved = ResolvedContext.from_environment(backend=backend)

    assert resolved.spawn_id is None
    assert resolved.depth == 0
    assert resolved.repo_root is None
    assert resolved.state_root is None
    assert resolved.chat_id == ""
    assert resolved.work_id is None
    assert resolved.work_dir is None
    assert resolved.fs_dir is None
    assert backend.session_lookup_calls == []
    assert backend.work_dir_calls == []


def test_from_environment_prefers_explicit_work_id(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_meridian_env(monkeypatch)
    repo_root = Path("/repo")
    state_root = Path("/runtime/state")
    backend = FakeBackend()

    monkeypatch.setenv("MERIDIAN_REPO_ROOT", repo_root.as_posix())
    monkeypatch.setenv("MERIDIAN_STATE_ROOT", state_root.as_posix())
    monkeypatch.setenv("MERIDIAN_WORK_ID", "work-from-env")

    resolved = ResolvedContext.from_environment(
        explicit_work_id="  explicit-work  ",
        backend=backend,
    )

    assert resolved.work_id == "explicit-work"
    assert backend.session_lookup_calls == []
    assert backend.work_dir_calls == [(Path("/repo/.meridian"), "explicit-work")]


def test_from_environment_uses_meridian_work_id(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_meridian_env(monkeypatch)
    repo_root = Path("/repo")
    backend = FakeBackend()

    monkeypatch.setenv("MERIDIAN_REPO_ROOT", repo_root.as_posix())
    monkeypatch.setenv("MERIDIAN_WORK_ID", "work-from-env")

    resolved = ResolvedContext.from_environment(backend=backend)

    assert resolved.work_id == "work-from-env"
    assert resolved.work_dir == Path("/repo/.meridian/work/resolved/work-from-env")
    assert resolved.fs_dir == Path("/repo/.meridian/fs")
    assert backend.session_lookup_calls == []
    assert backend.work_dir_calls == [(Path("/repo/.meridian"), "work-from-env")]


def test_from_environment_falls_back_to_session_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_meridian_env(monkeypatch)
    state_root = Path("/runtime/state")
    backend = FakeBackend(session_active_work_id="active-work", work_dir_suffix="fallback")

    monkeypatch.setenv("MERIDIAN_STATE_ROOT", state_root.as_posix())
    monkeypatch.setenv("MERIDIAN_CHAT_ID", "c42")

    resolved = ResolvedContext.from_environment(backend=backend)

    assert resolved.work_id == "active-work"
    assert resolved.work_dir == Path("/runtime/state/work/fallback/active-work")
    assert backend.session_lookup_calls == [(state_root, "c42")]
    assert backend.work_dir_calls == [(state_root, "active-work")]


def test_child_env_overrides_output_format() -> None:
    resolved = ResolvedContext(
        depth=2,
        repo_root=Path("/repo"),
        state_root=Path("/runtime/state"),
        chat_id="c9",
        work_id="work-123",
        work_dir=Path("/repo/.meridian/work/work-123"),
        fs_dir=Path("/repo/.meridian/fs"),
    )

    overrides = resolved.child_env_overrides()

    assert overrides == {
        "MERIDIAN_DEPTH": "3",
        "MERIDIAN_REPO_ROOT": "/repo",
        "MERIDIAN_STATE_ROOT": "/runtime/state",
        "MERIDIAN_CHAT_ID": "c9",
        "MERIDIAN_WORK_ID": "work-123",
        "MERIDIAN_WORK_DIR": "/repo/.meridian/work/work-123",
        "MERIDIAN_FS_DIR": "/repo/.meridian/fs",
    }
    assert resolved.child_env_overrides(increment_depth=False)["MERIDIAN_DEPTH"] == "2"


def test_resolved_context_is_frozen() -> None:
    resolved = ResolvedContext(depth=1)

    with pytest.raises(FrozenInstanceError):
        resolved.depth = 2  # type: ignore[misc]


def test_work_dir_prefers_repo_state_root_over_runtime_state_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_meridian_env(monkeypatch)
    backend = FakeBackend()

    monkeypatch.setenv("MERIDIAN_REPO_ROOT", "/repo")
    monkeypatch.setenv("MERIDIAN_STATE_ROOT", "/runtime/state")
    monkeypatch.setenv("MERIDIAN_WORK_ID", "selected-work")

    resolved = ResolvedContext.from_environment(backend=backend)

    assert resolved.work_dir == Path("/repo/.meridian/work/resolved/selected-work")
    assert backend.work_dir_calls == [(Path("/repo/.meridian"), "selected-work")]
