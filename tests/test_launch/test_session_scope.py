from __future__ import annotations

from pathlib import Path

import pytest

from meridian.lib.launch.session_scope import ManagedSession, session_scope


def _state_root(tmp_path: Path) -> Path:
    state_root = tmp_path / ".meridian"
    state_root.mkdir(parents=True, exist_ok=True)
    return state_root


def test_session_scope_starts_and_stops_session(tmp_path: Path) -> None:
    state_root = _state_root(tmp_path)
    start_calls: list[tuple[Path, str, str, str]] = []
    stop_calls: list[tuple[Path, str]] = []

    def fake_start_session(
        state_root_arg: Path,
        *,
        harness: str,
        harness_session_id: str,
        model: str,
        **_: object,
    ) -> str:
        start_calls.append((state_root_arg, harness, harness_session_id, model))
        return "c101"

    def fake_stop_session(state_root_arg: Path, chat_id: str) -> None:
        stop_calls.append((state_root_arg, chat_id))

    with session_scope(
        state_root=state_root,
        harness="codex",
        harness_session_id="seed-session",
        model="gpt-5.4",
        _start_session=fake_start_session,
        _stop_session=fake_stop_session,
    ) as managed:
        assert managed.chat_id == "c101"

    assert start_calls == [(state_root, "codex", "seed-session", "gpt-5.4")]
    assert stop_calls == [(state_root, "c101")]


def test_session_scope_stops_on_exception(tmp_path: Path) -> None:
    state_root = _state_root(tmp_path)
    stop_calls: list[tuple[Path, str]] = []

    def fake_start_session(
        _: Path,
        *,
        harness: str,
        harness_session_id: str,
        model: str,
        **__: object,
    ) -> str:
        _ = (harness, harness_session_id, model)
        return "c202"

    def fake_stop_session(state_root_arg: Path, chat_id: str) -> None:
        stop_calls.append((state_root_arg, chat_id))

    with pytest.raises(RuntimeError, match="boom"):
        with session_scope(
            state_root=state_root,
            harness="codex",
            harness_session_id="seed-session",
            model="gpt-5.4",
            _start_session=fake_start_session,
            _stop_session=fake_stop_session,
        ):
            raise RuntimeError("boom")

    assert stop_calls == [(state_root, "c202")]


def test_session_scope_yields_managed_session_with_chat_id(tmp_path: Path) -> None:
    state_root = _state_root(tmp_path)

    def fake_start_session(
        _: Path,
        *,
        harness: str,
        harness_session_id: str,
        model: str,
        **__: object,
    ) -> str:
        _ = (harness, harness_session_id, model)
        return "c303"

    with session_scope(
        state_root=state_root,
        harness="codex",
        harness_session_id="seed-session",
        model="gpt-5.4",
        _start_session=fake_start_session,
        _stop_session=lambda *_: None,
    ) as managed:
        assert managed == ManagedSession(chat_id="c303", record_harness_session_id=managed.record_harness_session_id)
        assert managed.chat_id == "c303"


def test_session_scope_record_harness_session_id_callback(tmp_path: Path) -> None:
    state_root = _state_root(tmp_path)
    update_calls: list[tuple[Path, str, str]] = []

    def fake_start_session(
        _: Path,
        *,
        harness: str,
        harness_session_id: str,
        model: str,
        **__: object,
    ) -> str:
        _ = (harness, harness_session_id, model)
        return "c404"

    def fake_update_session_harness_id(
        state_root_arg: Path,
        chat_id: str,
        harness_session_id: str,
    ) -> None:
        update_calls.append((state_root_arg, chat_id, harness_session_id))

    with session_scope(
        state_root=state_root,
        harness="codex",
        harness_session_id="seed-session",
        model="gpt-5.4",
        _start_session=fake_start_session,
        _stop_session=lambda *_: None,
        _update_session_harness_id=fake_update_session_harness_id,
    ) as managed:
        managed.record_harness_session_id("resolved-session")

    assert update_calls == [(state_root, "c404", "resolved-session")]


def test_session_scope_passes_all_params_to_start_session(tmp_path: Path) -> None:
    state_root = _state_root(tmp_path)
    captured: dict[str, object] = {}

    def fake_start_session(state_root_arg: Path, **kwargs: object) -> str:
        captured["state_root"] = state_root_arg
        captured["kwargs"] = kwargs
        return "c505"

    with session_scope(
        state_root=state_root,
        harness="codex",
        harness_session_id="seed-session",
        model="gpt-5.4",
        chat_id="c500",
        params=("--unsafe", "--json"),
        agent="implementer",
        agent_path="/tmp/agent.md",
        skills=("a", "b"),
        skill_paths=("/tmp/a/SKILL.md", "/tmp/b/SKILL.md"),
        _start_session=fake_start_session,
        _stop_session=lambda *_: None,
    ):
        pass

    assert captured["state_root"] == state_root
    assert captured["kwargs"] == {
        "harness": "codex",
        "harness_session_id": "seed-session",
        "model": "gpt-5.4",
        "chat_id": "c500",
        "params": ("--unsafe", "--json"),
        "agent": "implementer",
        "agent_path": "/tmp/agent.md",
        "skills": ("a", "b"),
        "skill_paths": ("/tmp/a/SKILL.md", "/tmp/b/SKILL.md"),
    }
