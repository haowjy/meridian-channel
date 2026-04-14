from __future__ import annotations

import socket
from pathlib import Path

import pytest

from meridian.lib.core.types import SpawnId
from meridian.lib.ops.spawn.authorization import AuthorizationDecision, PeercredFailure
from meridian.lib.streaming.control_socket import ControlSocketServer
from meridian.lib.streaming.types import InjectResult


class _FakeManager:
    def __init__(self, *, state_root: Path) -> None:
        self.state_root = state_root
        self.interrupt_calls = 0

    async def inject(self, *_args: object, **_kwargs: object) -> InjectResult:
        return InjectResult(success=True)

    async def interrupt(self, *_args: object, **_kwargs: object) -> InjectResult:
        self.interrupt_calls += 1
        return InjectResult(success=True, inbound_seq=7)

    async def cancel(self, *_args: object, **_kwargs: object) -> InjectResult:
        return InjectResult(success=True)


class _FakeWriter:
    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock

    def get_extra_info(self, name: str, default: object | None = None) -> object | None:
        if name == "socket":
            return self._sock
        return default


@pytest.mark.asyncio
async def test_interrupt_request_denies_when_peercred_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manager = _FakeManager(state_root=tmp_path / ".meridian")
    server = ControlSocketServer(SpawnId("p1"), tmp_path / "control.sock", manager)
    left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    writer = _FakeWriter(right)

    def _raise_peercred(_sock: socket.socket | None) -> tuple[SpawnId | None, int]:
        raise PeercredFailure("no peer creds")

    monkeypatch.setattr(
        "meridian.lib.streaming.control_socket.caller_from_socket_peer",
        _raise_peercred,
    )

    try:
        result = await server._handle_request(b'{"type":"interrupt"}\n', writer)
    finally:
        left.close()
        right.close()

    assert result == {"ok": False, "error": "caller identity unavailable"}
    assert manager.interrupt_calls == 0


@pytest.mark.asyncio
async def test_interrupt_request_denies_when_caller_not_authorized(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manager = _FakeManager(state_root=tmp_path / ".meridian")
    server = ControlSocketServer(SpawnId("p1"), tmp_path / "control.sock", manager)
    left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    writer = _FakeWriter(right)

    monkeypatch.setattr(
        "meridian.lib.streaming.control_socket.caller_from_socket_peer",
        lambda _sock: (SpawnId("p2"), 1),
    )
    monkeypatch.setattr(
        "meridian.lib.streaming.control_socket.authorize",
        lambda **_kwargs: AuthorizationDecision(
            allowed=False,
            reason="not_in_ancestry",
            caller_id=SpawnId("p2"),
            target_id=SpawnId("p1"),
        ),
    )

    try:
        result = await server._handle_request(b'{"type":"interrupt"}\n', writer)
    finally:
        left.close()
        right.close()

    assert result == {"ok": False, "error": "interrupt requires caller authorization"}
    assert manager.interrupt_calls == 0


@pytest.mark.asyncio
async def test_interrupt_request_routes_when_authorized(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manager = _FakeManager(state_root=tmp_path / ".meridian")
    server = ControlSocketServer(SpawnId("p1"), tmp_path / "control.sock", manager)
    left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    writer = _FakeWriter(right)

    monkeypatch.setattr(
        "meridian.lib.streaming.control_socket.caller_from_socket_peer",
        lambda _sock: (SpawnId("p1"), 1),
    )
    monkeypatch.setattr(
        "meridian.lib.streaming.control_socket.authorize",
        lambda **_kwargs: AuthorizationDecision(
            allowed=True,
            reason="self",
            caller_id=SpawnId("p1"),
            target_id=SpawnId("p1"),
        ),
    )

    try:
        result = await server._handle_request(b'{"type":"interrupt"}\n', writer)
    finally:
        left.close()
        right.close()

    assert result == {"ok": True, "inbound_seq": 7}
    assert manager.interrupt_calls == 1
