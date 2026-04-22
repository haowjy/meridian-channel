from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from meridian.lib.core.types import HarnessId, SpawnId
from meridian.lib.harness.connections.base import ConnectionConfig, HarnessEvent
from meridian.lib.harness.connections.codex_ws import CodexConnection
from meridian.lib.harness.launch_spec import CodexLaunchSpec
from meridian.lib.harness.projections import project_codex_subprocess as codex_subprocess_projection
from meridian.lib.harness.projections.project_codex_streaming import (
    HarnessCapabilityMismatch,
    project_codex_spec_to_appserver_command,
)
from meridian.lib.safety.permissions import (
    PermissionConfig,
    TieredPermissionResolver,
    UnsafeNoOpPermissionResolver,
)


class _FakeWebSocket:
    def __init__(self, messages: list[str]) -> None:
        self._messages = iter(messages)
        self.sent: list[str] = []
        self.closed = False

    async def send(self, data: str) -> None:
        self.sent.append(data)

    async def close(self) -> None:
        self.closed = True

    def __aiter__(self) -> _FakeWebSocket:
        return self

    async def __anext__(self) -> str:
        try:
            return next(self._messages)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class _TestableCodexConnection(CodexConnection):
    def attach_websocket(self, ws: _FakeWebSocket) -> None:
        self._state = "connected"
        self._ws = ws

    def set_launch_spec_for_test(self, spec: CodexLaunchSpec) -> None:
        self._launch_spec = spec

    def thread_bootstrap_request_for_test(
        self,
        config: ConnectionConfig,
        spec: CodexLaunchSpec,
    ) -> tuple[str, dict[str, object]]:
        self._config = config
        return self._thread_bootstrap_request(spec)

    async def run_reader(self) -> None:
        await self._read_messages_loop()

    async def next_event(self):  # type: ignore[override]
        return await self._event_queue.get()


def _build_config(tmp_path: Path) -> ConnectionConfig:
    return ConnectionConfig(
        spawn_id=SpawnId("p321"),
        harness_id=HarnessId.CODEX,
        prompt="hello",
        project_root=tmp_path,
        env_overrides={},
    )


def _values_for_setting(command: list[str], key: str) -> list[str]:
    values: list[str] = []
    for index, token in enumerate(command):
        if token != "-c":
            continue
        if index + 1 >= len(command):
            continue
        setting = command[index + 1]
        prefix = f"{key}="
        if setting.startswith(prefix):
            values.append(setting[len(prefix) :])
    return values


@pytest.mark.asyncio
async def test_codex_ws_auto_accepts_command_execution_approval_requests() -> None:
    message = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "req-1",
            "method": "item/commandExecution/requestApproval",
            "params": {
                "threadId": "thread-1",
                "turnId": "turn-1",
                "itemId": "call-1",
            },
        }
    )
    ws = _FakeWebSocket([message])
    connection = _TestableCodexConnection()
    connection.attach_websocket(ws)

    await connection.run_reader()

    assert [json.loads(payload) for payload in ws.sent] == [
        {
            "jsonrpc": "2.0",
            "id": "req-1",
            "result": {"decision": "accept"},
        }
    ]
    assert await connection.next_event() is None


@pytest.mark.asyncio
async def test_codex_ws_rejects_approval_requests_in_confirm_mode_and_emits_warning_event(
    caplog: pytest.LogCaptureFixture,
) -> None:
    message = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "req-2",
            "method": "item/fileChange/requestApproval",
            "params": {
                "threadId": "thread-1",
                "turnId": "turn-1",
                "itemId": "call-2",
            },
        }
    )
    ws = _FakeWebSocket([message])
    connection = _TestableCodexConnection()
    connection.attach_websocket(ws)
    connection.set_launch_spec_for_test(
        CodexLaunchSpec(
            permission_resolver=TieredPermissionResolver(
                config=PermissionConfig(approval="confirm")
            )
        )
    )

    with caplog.at_level("WARNING"):
        await connection.run_reader()

    assert "Rejecting Codex server approval request in confirm mode" in caplog.text

    warning_event = await connection.next_event()
    assert isinstance(warning_event, HarnessEvent)
    assert warning_event.event_type == "warning/approvalRejected"
    assert warning_event.payload == {
        "reason": "confirm_mode",
        "method": "item/fileChange/requestApproval",
    }

    assert [json.loads(payload) for payload in ws.sent] == [
        {
            "jsonrpc": "2.0",
            "id": "req-2",
            "error": {
                "code": -32000,
                "message": (
                    "Codex websocket approval requests are unsupported in confirm mode."
                ),
            },
        }
    ]
    assert await connection.next_event() is None


@pytest.mark.asyncio
async def test_codex_ws_confirm_mode_enqueues_rejection_event_before_send_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "req-3",
            "method": "item/commandExecution/requestApproval",
            "params": {
                "threadId": "thread-1",
                "turnId": "turn-1",
                "itemId": "call-3",
            },
        }
    )
    ws = _FakeWebSocket([message])
    connection = _TestableCodexConnection()
    connection.attach_websocket(ws)
    connection.set_launch_spec_for_test(
        CodexLaunchSpec(
            permission_resolver=TieredPermissionResolver(
                config=PermissionConfig(approval="confirm")
            )
        )
    )

    sequence: list[str] = []

    async def _fake_send_jsonrpc_error(
        request_id: object,
        *,
        code: int,
        message: str,
    ) -> None:
        _ = request_id, code, message
        sequence.append("send_error")
        queued = connection._event_queue.get_nowait()
        assert isinstance(queued, HarnessEvent)
        sequence.append(f"queue_head={queued.event_type}")
        await connection._event_queue.put(queued)

    monkeypatch.setattr(connection, "_send_jsonrpc_error", _fake_send_jsonrpc_error)

    await connection.run_reader()

    assert sequence == ["send_error", "queue_head=warning/approvalRejected"]
    assert ws.sent == []

    warning_event = await connection.next_event()
    assert isinstance(warning_event, HarnessEvent)
    assert warning_event.event_type == "warning/approvalRejected"
    assert await connection.next_event() is None


@pytest.mark.asyncio
async def test_codex_ws_rejects_unsupported_server_requests_explicitly() -> None:
    message = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "item/tool/call",
            "params": {
                "threadId": "thread-1",
                "turnId": "turn-1",
                "callId": "tool-1",
                "tool": "lookup_ticket",
                "arguments": {"id": "ABC-123"},
            },
        }
    )
    ws = _FakeWebSocket([message])
    connection = _TestableCodexConnection()
    connection.attach_websocket(ws)

    await connection.run_reader()

    warning_event = await connection.next_event()
    assert warning_event is not None
    assert warning_event.event_type == "warning/unsupportedServerRequest"
    assert warning_event.payload["method"] == "item/tool/call"
    assert [json.loads(payload) for payload in ws.sent] == [
        {
            "jsonrpc": "2.0",
            "id": 9,
            "error": {
                "code": -32601,
                "message": (
                    "Meridian codex_ws adapter does not support server request "
                    "'item/tool/call'"
                ),
            },
        }
    ]
    assert await connection.next_event() is None


def test_codex_streaming_projection_builds_appserver_command_and_logs_ignored_report_path(
    caplog: pytest.LogCaptureFixture,
) -> None:
    spec = CodexLaunchSpec(
        permission_resolver=TieredPermissionResolver(
            config=PermissionConfig(sandbox="read-only", approval="auto")
        ),
        report_output_path="report.md",
        extra_args=("--invalid-flag",),
    )

    with caplog.at_level(
        logging.DEBUG, logger="meridian.lib.harness.projections.project_codex_streaming"
    ):
        command = project_codex_spec_to_appserver_command(
            spec,
            host="127.0.0.1",
            port=7777,
        )

    assert command[:4] == ["codex", "app-server", "--listen", "ws://127.0.0.1:7777"]
    assert _values_for_setting(command, "sandbox_mode") == ['"read-only"']
    assert _values_for_setting(command, "approval_policy") == ['"on-request"']
    assert command[-1:] == ["--invalid-flag"]
    assert (
        "Codex streaming ignores report_output_path; reports extracted from artifacts"
        in caplog.text
    )
    assert "Forwarding passthrough args to codex app-server: ['--invalid-flag']" in caplog.text


def test_codex_streaming_projection_default_approval_emits_no_policy_override(
    tmp_path: Path,
) -> None:
    spec = CodexLaunchSpec(
        permission_resolver=TieredPermissionResolver(
            config=PermissionConfig(sandbox="workspace-write", approval="default")
        ),
    )

    command = project_codex_spec_to_appserver_command(
        spec,
        host="127.0.0.1",
        port=7778,
    )
    assert _values_for_setting(command, "approval_policy") == []
    assert _values_for_setting(command, "sandbox_mode") == ['"workspace-write"']

    connection = _TestableCodexConnection()
    method, payload = connection.thread_bootstrap_request_for_test(
        _build_config(tmp_path),
        spec,
    )
    assert method == "thread/start"
    assert "approvalPolicy" not in payload
    assert payload["sandbox"] == "workspace-write"


def test_codex_streaming_projection_with_no_overrides_emits_clean_baseline_command(
    caplog: pytest.LogCaptureFixture,
) -> None:
    spec = CodexLaunchSpec(
        permission_resolver=TieredPermissionResolver(config=PermissionConfig())
    )

    with caplog.at_level(
        logging.DEBUG, logger="meridian.lib.harness.projections.project_codex_streaming"
    ):
        command = project_codex_spec_to_appserver_command(
            spec,
            host="127.0.0.1",
            port=7779,
        )

    assert command == ["codex", "app-server", "--listen", "ws://127.0.0.1:7779"]
    assert "Forwarding passthrough args to codex app-server" not in caplog.text
    assert "Codex streaming ignores report_output_path" not in caplog.text


def test_codex_streaming_projection_keeps_colliding_passthrough_config_args(
    caplog: pytest.LogCaptureFixture,
) -> None:
    spec = CodexLaunchSpec(
        permission_resolver=TieredPermissionResolver(
            config=PermissionConfig(sandbox="read-only", approval="auto")
        ),
        extra_args=(
            "-c",
            'approval_policy="untrusted"',
            "-c",
            'sandbox_mode="workspace-write"',
        ),
    )

    with caplog.at_level(
        logging.DEBUG, logger="meridian.lib.harness.projections.project_codex_streaming"
    ):
        command = project_codex_spec_to_appserver_command(
            spec,
            host="127.0.0.1",
            port=7780,
        )

    assert _values_for_setting(command, "approval_policy") == ['"on-request"', '"untrusted"']
    assert _values_for_setting(command, "sandbox_mode") == ['"read-only"', '"workspace-write"']
    assert command[-4:] == [
        "-c",
        'approval_policy="untrusted"',
        "-c",
        'sandbox_mode="workspace-write"',
    ]
    assert (
        "Forwarding passthrough args to codex app-server: ['-c', "
        '\'approval_policy="untrusted"\', \'-c\', \'sandbox_mode="workspace-write"\']'
    ) in caplog.text


def test_codex_ws_thread_bootstrap_request_starts_new_thread(tmp_path: Path) -> None:
    connection = _TestableCodexConnection()

    method, payload = connection.thread_bootstrap_request_for_test(
        _build_config(tmp_path),
        CodexLaunchSpec(
            prompt="hello",
            model="gpt-5.3-codex",
            permission_resolver=UnsafeNoOpPermissionResolver(_suppress_warning=True),
        ),
    )

    assert method == "thread/start"
    assert payload == {"cwd": str(tmp_path), "model": "gpt-5.3-codex"}


def test_codex_ws_thread_bootstrap_request_projects_effort_and_permission_config(
    tmp_path: Path,
) -> None:
    connection = _TestableCodexConnection()

    method, payload = connection.thread_bootstrap_request_for_test(
        _build_config(tmp_path),
        CodexLaunchSpec(
            prompt="hello",
            model="gpt-5.3-codex",
            effort="high",
            permission_resolver=TieredPermissionResolver(
                config=PermissionConfig(sandbox="read-only", approval="auto")
            ),
        ),
    )

    assert method == "thread/start"
    assert payload == {
        "cwd": str(tmp_path),
        "model": "gpt-5.3-codex",
        "config": {"model_reasoning_effort": "high"},
        "approvalPolicy": "on-request",
        "sandbox": "read-only",
    }


def test_codex_ws_thread_bootstrap_request_resumes_existing_thread(tmp_path: Path) -> None:
    connection = _TestableCodexConnection()

    method, payload = connection.thread_bootstrap_request_for_test(
        _build_config(tmp_path),
        CodexLaunchSpec(
            prompt="hello",
            model="gpt-5.3-codex",
            continue_session_id="thread-123",
            permission_resolver=TieredPermissionResolver(
                config=PermissionConfig(approval="confirm")
            ),
        ),
    )

    assert method == "thread/resume"
    assert payload == {
        "cwd": str(tmp_path),
        "model": "gpt-5.3-codex",
        "approvalPolicy": "untrusted",
        "threadId": "thread-123",
    }


def test_codex_ws_thread_bootstrap_request_forks_existing_thread(tmp_path: Path) -> None:
    connection = _TestableCodexConnection()

    method, payload = connection.thread_bootstrap_request_for_test(
        _build_config(tmp_path),
        CodexLaunchSpec(
            prompt="hello",
            model="gpt-5.3-codex",
            continue_session_id="thread-123",
            continue_fork=True,
            permission_resolver=TieredPermissionResolver(
                config=PermissionConfig(sandbox="workspace-write", approval="default")
            ),
        ),
    )

    assert method == "thread/fork"
    assert payload == {
        "cwd": str(tmp_path),
        "model": "gpt-5.3-codex",
        "threadId": "thread-123",
        "sandbox": "workspace-write",
        "ephemeral": False,
    }


def test_codex_ws_thread_bootstrap_fails_closed_on_unmappable_permission_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _TestableCodexConnection()
    monkeypatch.setitem(codex_subprocess_projection._APPROVAL_POLICY_BY_MODE, "confirm", None)

    with pytest.raises(HarnessCapabilityMismatch, match="approval mode 'confirm'"):
        connection.thread_bootstrap_request_for_test(
            _build_config(tmp_path),
            CodexLaunchSpec(
                prompt="hello",
                permission_resolver=TieredPermissionResolver(
                    config=PermissionConfig(approval="confirm")
                ),
            ),
        )
