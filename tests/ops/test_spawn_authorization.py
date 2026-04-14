from __future__ import annotations

import socket
from pathlib import Path

import pytest

from meridian.lib.core.types import SpawnId
from meridian.lib.ops.spawn.authorization import (
    PeercredFailure,
    _caller_from_socket_peer,
    authorize,
    caller_from_env,
)
from meridian.lib.state import spawn_store


def _state_root(tmp_path: Path) -> Path:
    state_root = tmp_path / ".meridian"
    state_root.mkdir(parents=True, exist_ok=True)
    return state_root


def _create_spawn(
    state_root: Path,
    spawn_id: str,
    *,
    parent_id: str | None = None,
) -> None:
    spawn_store.start_spawn(
        state_root,
        chat_id="c1",
        parent_id=parent_id,
        model="gpt-5.4",
        agent="coder",
        harness="codex",
        prompt="hello",
        spawn_id=spawn_id,
    )


def test_authorize_allows_operator_at_depth_zero(tmp_path: Path) -> None:
    state_root = _state_root(tmp_path)
    _create_spawn(state_root, "p1")

    decision = authorize(
        state_root=state_root,
        target=SpawnId("p1"),
        caller=None,
        depth=0,
    )

    assert decision.allowed is True
    assert decision.reason == "operator"


def test_authorize_denies_missing_caller_inside_spawn(tmp_path: Path) -> None:
    state_root = _state_root(tmp_path)
    _create_spawn(state_root, "p1")

    decision = authorize(
        state_root=state_root,
        target=SpawnId("p1"),
        caller=None,
        depth=2,
    )

    assert decision.allowed is False
    assert decision.reason == "missing_caller_in_spawn"


def test_authorize_allows_self_caller(tmp_path: Path) -> None:
    state_root = _state_root(tmp_path)
    _create_spawn(state_root, "p1")

    decision = authorize(
        state_root=state_root,
        target=SpawnId("p1"),
        caller=SpawnId("p1"),
        depth=1,
    )

    assert decision.allowed is True
    assert decision.reason == "self"


def test_authorize_allows_ancestor_caller(tmp_path: Path) -> None:
    state_root = _state_root(tmp_path)
    _create_spawn(state_root, "p1")
    _create_spawn(state_root, "p2", parent_id="p1")
    _create_spawn(state_root, "p3", parent_id="p2")

    decision = authorize(
        state_root=state_root,
        target=SpawnId("p3"),
        caller=SpawnId("p1"),
        depth=2,
    )

    assert decision.allowed is True
    assert decision.reason == "ancestor"


def test_authorize_denies_non_ancestor_caller(tmp_path: Path) -> None:
    state_root = _state_root(tmp_path)
    _create_spawn(state_root, "p1")
    _create_spawn(state_root, "p2", parent_id="p1")
    _create_spawn(state_root, "p9")

    decision = authorize(
        state_root=state_root,
        target=SpawnId("p2"),
        caller=SpawnId("p9"),
        depth=1,
    )

    assert decision.allowed is False
    assert decision.reason == "not_in_ancestry"


def test_authorize_denies_missing_target(tmp_path: Path) -> None:
    state_root = _state_root(tmp_path)
    _create_spawn(state_root, "p1")

    decision = authorize(
        state_root=state_root,
        target=SpawnId("p404"),
        caller=SpawnId("p1"),
        depth=1,
    )

    assert decision.allowed is False
    assert decision.reason == "missing_target"


def test_caller_from_env_reads_spawn_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MERIDIAN_SPAWN_ID", " p12 ")
    monkeypatch.setenv("MERIDIAN_DEPTH", " 3 ")

    caller, depth = caller_from_env()

    assert caller == SpawnId("p12")
    assert depth == 3


def test_caller_from_socket_peer_requires_socket() -> None:
    with pytest.raises(PeercredFailure, match="missing peer socket"):
        _caller_from_socket_peer(None)


def test_caller_from_socket_peer_rejects_non_unix_socket() -> None:
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(PeercredFailure, match="not an AF_UNIX socket"):
            _caller_from_socket_peer(tcp_socket)
    finally:
        tcp_socket.close()
