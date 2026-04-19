from __future__ import annotations

import asyncio
import json
import signal
from typing import get_args, get_origin

import pytest

from meridian.lib.harness.connections.base import HarnessConnection
from meridian.lib.harness.connections.claude_ws import ClaudeConnection
from meridian.lib.harness.connections.codex_ws import CodexConnection
from meridian.lib.harness.connections.opencode_http import OpenCodeConnection
from meridian.lib.harness.launch_spec import (
    ClaudeLaunchSpec,
    CodexLaunchSpec,
    OpenCodeLaunchSpec,
)


class _LoopbackCodexWebSocket:
    def __init__(self) -> None:
        self._responses: asyncio.Queue[str | None] = asyncio.Queue()
        self.sent_payloads: list[dict[str, object]] = []
        self.close_calls = 0

    async def send(self, data: str) -> None:
        payload = json.loads(data)
        assert isinstance(payload, dict)
        message = payload
        self.sent_payloads.append(message)

        request_id = message.get("id")
        method = message.get("method")
        if request_id is not None and isinstance(method, str):
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {},
            }
            await self._responses.put(json.dumps(response))

    async def close(self) -> None:
        self.close_calls += 1
        await self._responses.put(None)

    def __aiter__(self) -> _LoopbackCodexWebSocket:
        return self

    async def __anext__(self) -> str:
        message = await self._responses.get()
        if message is None:
            raise StopAsyncIteration
        return message


class _FakeClaudeProcess:
    def __init__(self) -> None:
        self.returncode: int | None = None
        self.signals: list[signal.Signals] = []

    def send_signal(self, sig: signal.Signals) -> None:
        self.signals.append(sig)


class _FakeHttpResponse:
    def __init__(
        self,
        *,
        status: int = 202,
        content_type: str = "application/json",
    ) -> None:
        self.status = status
        self.headers = {"Content-Type": content_type}

    async def __aenter__(self) -> _FakeHttpResponse:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> bool:
        _ = exc_type, exc, tb
        return False

    async def text(self) -> str:
        return ""

    def release(self) -> None:
        return None


class _FakeOpenCodeHttpClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def post(self, url: str, *, json: dict[str, object]) -> _FakeHttpResponse:
        self.calls.append((url, dict(json)))
        return _FakeHttpResponse(status=202)


class _TestableCodexConnection(CodexConnection):
    def attach_connected_websocket(
        self,
        ws: _LoopbackCodexWebSocket,
        *,
        thread_id: str,
        turn_id: str,
    ) -> None:
        self._state = "connected"
        self._ws = ws
        self._thread_id = thread_id
        self._current_turn_id = turn_id

    async def run_reader(self) -> None:
        await self._read_messages_loop()


class _TestableClaudeConnection(ClaudeConnection):
    def attach_connected_process(self, process: _FakeClaudeProcess) -> None:
        self._state = "connected"
        self._process = process  # type: ignore[assignment]


class _TestableOpenCodeConnection(OpenCodeConnection):
    def attach_connected_client(
        self,
        client: _FakeOpenCodeHttpClient,
        *,
        base_url: str,
        session_id: str,
    ) -> None:
        self._state = "connected"
        self._base_url = base_url
        self._session_id = session_id
        self._client = client


def test_all_streaming_connections_bind_harness_connection_protocol() -> None:
    expected = (
        (ClaudeConnection, ClaudeLaunchSpec),
        (CodexConnection, CodexLaunchSpec),
        (OpenCodeConnection, OpenCodeLaunchSpec),
    )
    for connection_cls, expected_spec in expected:
        assert issubclass(connection_cls, HarnessConnection)
        matching_bases = [
            base
            for base in getattr(connection_cls, "__orig_bases__", ())
            if get_origin(base) is HarnessConnection
        ]
        assert matching_bases
        assert get_args(matching_bases[0]) == (expected_spec,)
        connection_cls()


@pytest.mark.asyncio
async def test_claude_connection_cancel_interrupt_are_idempotent() -> None:
    connection = _TestableClaudeConnection()
    process = _FakeClaudeProcess()
    connection.attach_connected_process(process)

    await connection.send_interrupt()
    await connection.send_interrupt()
    await connection.send_cancel()
    await connection.send_cancel()

    assert process.signals == [signal.SIGINT, signal.SIGINT]
    assert connection.state == "stopping"


@pytest.mark.asyncio
async def test_codex_connection_cancel_interrupt_are_idempotent() -> None:
    connection = _TestableCodexConnection()
    ws = _LoopbackCodexWebSocket()
    connection.attach_connected_websocket(ws, thread_id="thread-1", turn_id="turn-1")

    reader_task = asyncio.create_task(connection.run_reader())
    await connection.send_interrupt()
    await connection.send_interrupt()
    await connection.send_cancel()
    await connection.send_cancel()
    await asyncio.wait_for(reader_task, timeout=1.0)

    request_methods = [
        payload["method"]
        for payload in ws.sent_payloads
        if isinstance(payload.get("method"), str)
    ]
    assert request_methods == ["turn/interrupt"]
    assert ws.close_calls == 1
    assert connection.state == "stopping"


@pytest.mark.asyncio
async def test_opencode_connection_cancel_interrupt_are_idempotent() -> None:
    connection = _TestableOpenCodeConnection()
    client = _FakeOpenCodeHttpClient()
    connection.attach_connected_client(
        client,
        base_url="http://opencode.test",
        session_id="session-1",
    )

    await connection.send_interrupt()
    await connection.send_interrupt()
    await connection.send_cancel()
    await connection.send_cancel()

    assert len(client.calls) == 2
    assert client.calls[0][0].endswith("/session/session-1/abort")
    assert client.calls[1][0].endswith("/session/session-1/abort")
    assert client.calls[0][1] == {"response": "abort"}
    assert client.calls[1][1] == {"response": "abort"}
    assert connection.state == "stopping"
