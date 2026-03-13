from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from meridian.lib.ops import session_policy


@dataclass(frozen=True)
class _AutoWorkItem:
    name: str
    auto_generated: bool = True


def _state_root(tmp_path: Path) -> Path:
    state_root = tmp_path / ".meridian"
    state_root.mkdir(parents=True, exist_ok=True)
    return state_root


def test_ensure_session_work_item_returns_existing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_root = _state_root(tmp_path)
    update_calls: list[tuple[Path, str, str | None]] = []

    def fake_get_session_active_work_id(state_root_arg: Path, chat_id: str) -> str | None:
        assert state_root_arg == state_root
        assert chat_id == "c1"
        return "work-existing"

    def fake_create_auto_work_item(_: Path) -> _AutoWorkItem:
        raise AssertionError("create_auto_work_item should not be called when active work exists")

    def fake_update_session_work_id(
        state_root_arg: Path, chat_id: str, work_id: str | None
    ) -> None:
        update_calls.append((state_root_arg, chat_id, work_id))

    monkeypatch.setattr(session_policy, "get_session_active_work_id", fake_get_session_active_work_id)
    monkeypatch.setattr(session_policy.work_store, "create_auto_work_item", fake_create_auto_work_item)
    monkeypatch.setattr(session_policy, "update_session_work_id", fake_update_session_work_id)

    result = session_policy.ensure_session_work_item(state_root, "c1")

    assert result == "work-existing"
    assert update_calls == []


def test_ensure_session_work_item_creates_auto_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_root = _state_root(tmp_path)
    update_calls: list[tuple[Path, str, str | None]] = []

    def fake_get_session_active_work_id(state_root_arg: Path, chat_id: str) -> str | None:
        assert state_root_arg == state_root
        assert chat_id == "c2"
        return None

    def fake_create_auto_work_item(state_root_arg: Path) -> _AutoWorkItem:
        assert state_root_arg == state_root
        return _AutoWorkItem(name="work-auto-1")

    def fake_update_session_work_id(
        state_root_arg: Path, chat_id: str, work_id: str | None
    ) -> None:
        update_calls.append((state_root_arg, chat_id, work_id))

    monkeypatch.setattr(session_policy, "get_session_active_work_id", fake_get_session_active_work_id)
    monkeypatch.setattr(session_policy.work_store, "create_auto_work_item", fake_create_auto_work_item)
    monkeypatch.setattr(session_policy, "update_session_work_id", fake_update_session_work_id)

    result = session_policy.ensure_session_work_item(state_root, "c2")

    assert result == "work-auto-1"
    assert update_calls == [(state_root, "c2", "work-auto-1")]


def test_ensure_session_work_item_returns_created_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_root = _state_root(tmp_path)

    monkeypatch.setattr(session_policy, "get_session_active_work_id", lambda *_: None)
    monkeypatch.setattr(
        session_policy.work_store,
        "create_auto_work_item",
        lambda _: _AutoWorkItem(name="work-generated-42"),
    )
    monkeypatch.setattr(session_policy, "update_session_work_id", lambda *_: None)

    result = session_policy.ensure_session_work_item(state_root, "c3")

    assert result == "work-generated-42"


def test_ensure_session_work_item_inherits_parent_work_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When inherited_work_id is valid, use it instead of creating auto."""
    state_root = _state_root(tmp_path)
    update_calls: list[tuple[Path, str, str | None]] = []

    @dataclass(frozen=True)
    class _FakeWorkItem:
        name: str

    monkeypatch.setattr(session_policy, "get_session_active_work_id", lambda *_: None)
    monkeypatch.setattr(
        session_policy.work_store,
        "get_work_item",
        lambda _root, wid: _FakeWorkItem(name=wid) if wid == "parent-work" else None,
    )
    monkeypatch.setattr(
        session_policy.work_store,
        "create_auto_work_item",
        lambda _: (_ for _ in ()).throw(AssertionError("should not create auto")),
    )
    monkeypatch.setattr(
        session_policy,
        "update_session_work_id",
        lambda root, cid, wid: update_calls.append((root, cid, wid)),
    )

    result = session_policy.ensure_session_work_item(
        state_root, "c4", inherited_work_id="parent-work",
    )

    assert result == "parent-work"
    assert update_calls == [(state_root, "c4", "parent-work")]


def test_ensure_session_work_item_falls_back_to_auto_on_deleted_inherited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When inherited work item no longer exists, fall back to auto-create."""
    state_root = _state_root(tmp_path)

    monkeypatch.setattr(session_policy, "get_session_active_work_id", lambda *_: None)
    monkeypatch.setattr(session_policy.work_store, "get_work_item", lambda *_: None)
    monkeypatch.setattr(
        session_policy.work_store,
        "create_auto_work_item",
        lambda _: _AutoWorkItem(name="auto-fallback"),
    )
    monkeypatch.setattr(session_policy, "update_session_work_id", lambda *_: None)

    result = session_policy.ensure_session_work_item(
        state_root, "c5", inherited_work_id="deleted-work",
    )

    assert result == "auto-fallback"


def _create_auto_work_dir(state_root: Path, work_id: str) -> Path:
    """Create a minimal auto-generated work item directory."""
    work_dir = state_root / "work" / work_id
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "work.json").write_text(json.dumps({
        "name": work_id,
        "description": "",
        "status": "open",
        "created_at": "2026-01-01T00:00:00Z",
        "auto_generated": True,
    }))
    return work_dir


def test_cleanup_deletes_empty_auto_work_item(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty auto work item with no spawns or sessions is deleted."""
    state_root = _state_root(tmp_path)
    work_dir = _create_auto_work_dir(state_root, "empty-auto")

    monkeypatch.setattr(
        session_policy, "get_session_active_work_id", lambda *_: "empty-auto",
    )
    monkeypatch.setattr(session_policy, "list_active_sessions", lambda *_: [])
    monkeypatch.setattr(session_policy.spawn_store, "list_spawns", lambda *_a, **_kw: [])

    session_policy.cleanup_empty_auto_work_item(state_root, "c1")

    assert not work_dir.exists()


def test_cleanup_preserves_non_auto_work_item(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-auto work items are never deleted."""
    state_root = _state_root(tmp_path)
    work_dir = state_root / "work" / "my-feature"
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "work.json").write_text(json.dumps({
        "name": "my-feature",
        "description": "real work",
        "status": "open",
        "created_at": "2026-01-01T00:00:00Z",
        "auto_generated": False,
    }))

    monkeypatch.setattr(
        session_policy, "get_session_active_work_id", lambda *_: "my-feature",
    )
    monkeypatch.setattr(session_policy, "list_active_sessions", lambda *_: [])
    monkeypatch.setattr(session_policy.spawn_store, "list_spawns", lambda *_a, **_kw: [])

    session_policy.cleanup_empty_auto_work_item(state_root, "c1")

    assert work_dir.exists()


def test_cleanup_preserves_auto_work_item_with_spawns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auto work item with spawns is not deleted."""
    state_root = _state_root(tmp_path)
    work_dir = _create_auto_work_dir(state_root, "has-spawns")

    monkeypatch.setattr(
        session_policy, "get_session_active_work_id", lambda *_: "has-spawns",
    )
    monkeypatch.setattr(session_policy, "list_active_sessions", lambda *_: [])
    monkeypatch.setattr(
        session_policy.spawn_store, "list_spawns",
        lambda *_a, **_kw: [object()],  # non-empty
    )

    session_policy.cleanup_empty_auto_work_item(state_root, "c1")

    assert work_dir.exists()


def test_cleanup_preserves_auto_work_item_with_user_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auto work item with user-created files beyond work.json is not deleted."""
    state_root = _state_root(tmp_path)
    work_dir = _create_auto_work_dir(state_root, "has-notes")
    (work_dir / "design.md").write_text("important notes")

    monkeypatch.setattr(
        session_policy, "get_session_active_work_id", lambda *_: "has-notes",
    )
    monkeypatch.setattr(session_policy, "list_active_sessions", lambda *_: [])
    monkeypatch.setattr(session_policy.spawn_store, "list_spawns", lambda *_a, **_kw: [])

    session_policy.cleanup_empty_auto_work_item(state_root, "c1")

    assert work_dir.exists()


def test_cleanup_preserves_work_item_with_other_active_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auto work item still in use by another session is not deleted."""
    state_root = _state_root(tmp_path)
    work_dir = _create_auto_work_dir(state_root, "shared-work")

    def fake_get_work_id(_root: Path, chat_id: str) -> str | None:
        return "shared-work"

    monkeypatch.setattr(session_policy, "get_session_active_work_id", fake_get_work_id)
    monkeypatch.setattr(
        session_policy, "list_active_sessions", lambda *_: ["c1", "c2"],
    )
    monkeypatch.setattr(session_policy.spawn_store, "list_spawns", lambda *_a, **_kw: [])

    session_policy.cleanup_empty_auto_work_item(state_root, "c1")

    assert work_dir.exists()
