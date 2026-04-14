import asyncio
import json
import os
import signal
import sys
import textwrap
from itertools import pairwise
from pathlib import Path
from typing import ClassVar, get_args, get_origin

import pytest

from meridian.lib.core.domain import Spawn, TokenUsage
from meridian.lib.core.types import HarnessId, ModelId, SpawnId
from meridian.lib.harness.adapter import ArtifactStore as HarnessArtifactStore
from meridian.lib.harness.adapter import (
    BaseSubprocessHarness,
    HarnessCapabilities,
    McpConfig,
    PermissionResolver,
    SpawnParams,
    resolve_permission_flags,
)
from meridian.lib.harness.common import (
    extract_session_id_from_artifacts_with_patterns,
    extract_usage_from_artifacts,
)
from meridian.lib.harness.connections.base import HarnessConnection
from meridian.lib.harness.connections.claude_ws import ClaudeConnection
from meridian.lib.harness.connections.codex_ws import CodexConnection
from meridian.lib.harness.connections.opencode_http import OpenCodeConnection
from meridian.lib.harness.errors import HarnessBinaryNotFound
from meridian.lib.harness.launch_spec import (
    ClaudeLaunchSpec,
    CodexLaunchSpec,
    OpenCodeLaunchSpec,
)
from meridian.lib.harness.registry import HarnessRegistry
from meridian.lib.launch import runner as launch_runner
from meridian.lib.launch.launch_types import ResolvedLaunchSpec
from meridian.lib.launch.runner import execute_with_finalization, spawn_and_stream
from meridian.lib.ops.spawn.plan import ExecutionPolicy, PreparedSpawnPlan, SessionContinuation
from meridian.lib.safety.permissions import PermissionConfig, TieredPermissionResolver
from meridian.lib.state import spawn_store
from meridian.lib.state.artifact_store import LocalStore, make_artifact_key
from meridian.lib.state.paths import resolve_state_paths


class ScriptHarnessAdapter(BaseSubprocessHarness):
    id: ClassVar[HarnessId] = HarnessId.CODEX
    consumed_fields: ClassVar[frozenset[str]] = frozenset()
    explicitly_ignored_fields: ClassVar[frozenset[str]] = frozenset()

    def __init__(self, *, command: tuple[str, ...]) -> None:
        self._command = command

    @property
    def capabilities(self) -> HarnessCapabilities:
        return HarnessCapabilities()

    def resolve_launch_spec(
        self,
        run: SpawnParams,
        perms: PermissionResolver,
    ) -> ResolvedLaunchSpec:
        return ResolvedLaunchSpec(
            prompt=run.prompt or "",
            permission_resolver=perms,
        )

    def build_command(self, run: SpawnParams, perms: PermissionResolver) -> list[str]:
        return [*self._command, *resolve_permission_flags(perms, self.id), *run.extra_args]

    def env_overrides(self, config: PermissionConfig) -> dict[str, str]:
        _ = config
        return {}

    def mcp_config(self, run: SpawnParams) -> McpConfig | None:
        _ = run
        return None

    def extract_usage(self, artifacts: HarnessArtifactStore, spawn_id: SpawnId) -> TokenUsage:
        return extract_usage_from_artifacts(artifacts, spawn_id)

    def extract_session_id(self, artifacts: HarnessArtifactStore, spawn_id: SpawnId) -> str | None:
        return extract_session_id_from_artifacts_with_patterns(artifacts, spawn_id)


def _create_run(repo_root: Path, *, prompt: str, name: str = "exec") -> tuple[Spawn, Path]:
    run = Spawn(
        spawn_id=SpawnId("r1"),
        prompt=prompt,
        model=ModelId("gpt-5.3-codex"),
        status="queued",
    )
    return run, resolve_state_paths(repo_root).root_dir


def _fetch_run_row(state_root: Path, spawn_id: SpawnId) -> spawn_store.SpawnRecord:
    row = spawn_store.get_spawn(state_root, spawn_id)
    assert row is not None
    return row


def _write_script(path: Path, source: str) -> None:
    path.write_text(textwrap.dedent(source), encoding="utf-8")


def _read_output_payload(artifacts: LocalStore, spawn_id: SpawnId) -> dict[str, object]:
    raw = artifacts.get(make_artifact_key(spawn_id, "output.jsonl")).decode("utf-8")
    return json.loads(raw.strip())


def _build_plan(
    run: Spawn,
    harness_id: HarnessId,
    *,
    timeout_seconds: float | None = None,
    kill_grace_seconds: float = 30.0,
    max_retries: int = 0,
    retry_backoff_seconds: float = 2.0,
) -> PreparedSpawnPlan:
    return PreparedSpawnPlan(
        model=str(run.model),
        harness_id=str(harness_id),
        prompt=run.prompt,
        agent_name=None,
        skills=(),
        skill_paths=(),
        reference_files=(),
        template_vars={},
        mcp_tools=(),
        session_agent="",
        session_agent_path="",
        session=SessionContinuation(),
        execution=ExecutionPolicy(
            timeout_secs=timeout_seconds,
            kill_grace_secs=kill_grace_seconds,
            max_retries=max_retries,
            retry_backoff_secs=retry_backoff_seconds,
            permission_config=PermissionConfig(),
            permission_resolver=TieredPermissionResolver(config=PermissionConfig()),
            allowed_tools=(),
        ),
        cli_command=(),
    )


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
async def test_claude_connection_cancel_interrupt_are_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = ClaudeConnection()
    connection._state = "connected"
    signal_calls: list[signal.Signals] = []

    async def _fake_signal(sig: signal.Signals) -> None:
        signal_calls.append(sig)

    monkeypatch.setattr(connection, "_signal_process", _fake_signal)

    await connection.send_interrupt()
    await connection.send_interrupt()
    await connection.send_cancel()
    await connection.send_cancel()

    assert signal_calls == [signal.SIGINT, signal.SIGINT]
    assert connection.state == "stopping"


@pytest.mark.asyncio
async def test_codex_connection_cancel_interrupt_are_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = CodexConnection()
    connection._state = "connected"
    connection._thread_id = "thread-1"
    connection._current_turn_id = "turn-1"
    request_methods: list[str] = []
    close_calls = 0

    async def _fake_request(
        method: str,
        params: dict[str, object] | None = None,
        *,
        timeout_seconds: float | None = None,
    ) -> dict[str, object]:
        _ = params, timeout_seconds
        request_methods.append(method)
        return {}

    async def _fake_close_ws() -> None:
        nonlocal close_calls
        close_calls += 1

    monkeypatch.setattr(connection, "_request", _fake_request)
    monkeypatch.setattr(connection, "_close_ws", _fake_close_ws)

    await connection.send_interrupt()
    await connection.send_interrupt()
    await connection.send_cancel()
    await connection.send_cancel()

    assert request_methods == ["turn/interrupt"]
    assert close_calls == 1
    assert connection.state == "stopping"


@pytest.mark.asyncio
async def test_opencode_connection_cancel_interrupt_are_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = OpenCodeConnection()
    connection._state = "connected"
    connection._session_id = "session-1"
    action_calls = 0

    async def _fake_post_session_action(
        *,
        path_templates: tuple[str, ...],
        payload_variants: tuple[dict[str, object], ...],
        accepted_statuses: frozenset[int],
    ) -> None:
        _ = path_templates, payload_variants, accepted_statuses
        nonlocal action_calls
        action_calls += 1

    monkeypatch.setattr(connection, "_post_session_action", _fake_post_session_action)

    await connection.send_interrupt()
    await connection.send_interrupt()
    await connection.send_cancel()
    await connection.send_cancel()

    assert action_calls == 2
    assert connection.state == "stopping"


@pytest.mark.asyncio
async def test_spawn_and_stream_raises_structured_missing_binary_error(tmp_path: Path) -> None:
    artifacts = LocalStore(root_dir=tmp_path / ".artifacts")
    spawn_id = SpawnId("p-missing-binary")

    with pytest.raises(HarnessBinaryNotFound) as exc_info:
        await spawn_and_stream(
            spawn_id=spawn_id,
            command=("definitely-missing-binary-phase8-test",),
            cwd=tmp_path,
            artifacts=artifacts,
            output_log_path=tmp_path / "output.jsonl",
            stderr_log_path=tmp_path / "stderr.log",
            timeout_seconds=1.0,
            harness_id=HarnessId.CODEX,
        )

    err = exc_info.value
    assert err.harness_id == "codex"
    assert err.binary_name == "definitely-missing-binary-phase8-test"
    assert err.searched_path == str(os.environ.get("PATH", ""))


@pytest.mark.asyncio
async def test_execute_retries_retryable_errors_up_to_max(tmp_path: Path) -> None:
    run, state_root = _create_run(tmp_path, prompt="retry me")
    artifacts = LocalStore(root_dir=tmp_path / ".artifacts")

    counter = tmp_path / "retryable-count.txt"
    script = tmp_path / "retryable.py"
    _write_script(
        script,
        """
        from pathlib import Path
        import sys

        counter = Path(sys.argv[1])
        if counter.exists():
            value = int(counter.read_text(encoding="utf-8"))
        else:
            value = 0
        counter.write_text(str(value + 1), encoding="utf-8")
        print("network error: connection reset", file=sys.stderr, flush=True)
        raise SystemExit(1)
        """,
    )

    adapter = ScriptHarnessAdapter(command=(sys.executable, str(script), str(counter)))
    registry = HarnessRegistry()
    registry.register(adapter)

    exit_code = await execute_with_finalization(
        run,
        plan=_build_plan(
            run,
            adapter.id,
            max_retries=3,
            retry_backoff_seconds=0.0,
        ),
        repo_root=tmp_path,
        state_root=state_root,
        artifacts=artifacts,
        registry=registry,
        harness_id=adapter.id,
        cwd=tmp_path,
    )

    assert exit_code == 1
    assert counter.read_text(encoding="utf-8") == "4"
    row = _fetch_run_row(state_root, run.spawn_id)
    assert row.status == "failed"
    assert row.error is None


@pytest.mark.asyncio
async def test_execute_does_not_retry_unrecoverable_errors(tmp_path: Path) -> None:
    run, _state_root = _create_run(tmp_path, prompt="fail once")
    artifacts = LocalStore(root_dir=tmp_path / ".artifacts")

    counter = tmp_path / "unrecoverable-count.txt"
    script = tmp_path / "unrecoverable.py"
    _write_script(
        script,
        """
        from pathlib import Path
        import sys

        counter = Path(sys.argv[1])
        if counter.exists():
            value = int(counter.read_text(encoding="utf-8"))
        else:
            value = 0
        counter.write_text(str(value + 1), encoding="utf-8")
        print("model not found", file=sys.stderr, flush=True)
        raise SystemExit(1)
        """,
    )

    adapter = ScriptHarnessAdapter(command=(sys.executable, str(script), str(counter)))
    registry = HarnessRegistry()
    registry.register(adapter)

    exit_code = await execute_with_finalization(
        run,
        plan=_build_plan(
            run,
            adapter.id,
            max_retries=3,
            retry_backoff_seconds=0.0,
        ),
        repo_root=tmp_path,
        state_root=resolve_state_paths(tmp_path).root_dir,
        artifacts=artifacts,
        registry=registry,
        harness_id=adapter.id,
        cwd=tmp_path,
    )

    assert exit_code == 1
    assert counter.read_text(encoding="utf-8") == "1"


@pytest.mark.asyncio
async def test_execute_sets_timeout_failure_reason(tmp_path: Path) -> None:
    run, state_root = _create_run(tmp_path, prompt="timeout")
    artifacts = LocalStore(root_dir=tmp_path / ".artifacts")

    script = tmp_path / "timeout.py"
    _write_script(
        script,
        """
        import time

        time.sleep(2.0)
        """,
    )
    adapter = ScriptHarnessAdapter(command=(sys.executable, str(script)))
    registry = HarnessRegistry()
    registry.register(adapter)

    exit_code = await execute_with_finalization(
        run,
        plan=_build_plan(
            run,
            adapter.id,
            timeout_seconds=0.05,
            kill_grace_seconds=0.05,
            max_retries=3,
            retry_backoff_seconds=0.0,
        ),
        repo_root=tmp_path,
        state_root=state_root,
        artifacts=artifacts,
        registry=registry,
        harness_id=adapter.id,
        cwd=tmp_path,
    )

    assert exit_code == 3
    row = _fetch_run_row(state_root, run.spawn_id)
    assert row.status == "failed"
    assert row.error == "timeout"
    assert _read_output_payload(artifacts, run.spawn_id) == {
        "error_code": "harness_empty_output",
        "failure_reason": "timeout",
        "exit_code": 3,
        "timed_out": True,
    }


@pytest.mark.asyncio
async def test_execute_handles_large_stdout_json_lines(tmp_path: Path) -> None:
    run, state_root = _create_run(tmp_path, prompt="large line")
    artifacts = LocalStore(root_dir=tmp_path / ".artifacts")

    script = tmp_path / "large_line.py"
    _write_script(
        script,
        """
        import json
        import sys
        from pathlib import Path

        report_path = Path(sys.argv[1])
        payload = {"type": "tool_result", "content": "x" * 70000}
        print(json.dumps(payload), flush=True)
        report_path.write_text("# Large Line OK\\n", encoding="utf-8")
        print(json.dumps({"type": "result", "subtype": "success"}), flush=True)
        """,
    )

    class LargeLineHarnessAdapter(ScriptHarnessAdapter):
        def build_command(self, run: SpawnParams, perms: PermissionResolver) -> list[str]:
            return [
                *self._command,
                run.report_output_path or "",
                *resolve_permission_flags(perms, self.id),
                *run.extra_args,
            ]

    adapter = LargeLineHarnessAdapter(command=(sys.executable, str(script)))
    registry = HarnessRegistry()
    registry.register(adapter)

    exit_code = await execute_with_finalization(
        run,
        plan=_build_plan(
            run,
            adapter.id,
            max_retries=0,
        ),
        repo_root=tmp_path,
        state_root=state_root,
        artifacts=artifacts,
        registry=registry,
        harness_id=adapter.id,
        cwd=tmp_path,
    )

    assert exit_code == 0
    row = _fetch_run_row(state_root, run.spawn_id)
    assert row.status == "succeeded"
    output = artifacts.get(make_artifact_key(run.spawn_id, "output.jsonl")).decode("utf-8")
    assert '"type": "tool_result"' in output
    assert len(output) > 70000


@pytest.mark.asyncio
async def test_execute_treats_watchdog_termination_after_report_as_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run, state_root = _create_run(tmp_path, prompt="report then linger")
    artifacts = LocalStore(root_dir=tmp_path / ".artifacts")

    script = tmp_path / "report_then_linger.py"
    _write_script(
        script,
        """
        import json
        import sys
        import time
        from pathlib import Path

        report_path = Path(sys.argv[1])
        print(json.dumps({"type": "message", "text": "working"}), flush=True)
        report_path.write_text("# Finished\\n\\nActual work is done.\\n", encoding="utf-8")
        print(json.dumps({"type": "result", "subtype": "success"}), flush=True)
        time.sleep(5.0)
        """,
    )

    class ReportHarnessAdapter(ScriptHarnessAdapter):
        def build_command(self, run: SpawnParams, perms: PermissionResolver) -> list[str]:
            return [
                *self._command,
                run.report_output_path or "",
                *resolve_permission_flags(perms, self.id),
                *run.extra_args,
            ]

    async def fast_watchdog(
        report_path: Path,
        process: asyncio.subprocess.Process,
        grace_secs: float = 60.0,
    ) -> bool:
        _ = grace_secs
        while not report_path.exists():
            if process.returncode is not None:
                return False
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.05)
        if process.returncode is not None:
            return False
        await launch_runner.terminate_process(process, grace_seconds=0.05)
        return True

    adapter = ReportHarnessAdapter(command=(sys.executable, str(script)))
    registry = HarnessRegistry()
    registry.register(adapter)
    monkeypatch.setattr(launch_runner, "_report_watchdog", fast_watchdog)

    exit_code = await execute_with_finalization(
        run,
        plan=_build_plan(
            run,
            adapter.id,
            max_retries=0,
        ),
        repo_root=tmp_path,
        state_root=state_root,
        artifacts=artifacts,
        registry=registry,
        harness_id=adapter.id,
        cwd=tmp_path,
    )

    assert exit_code == 0
    row = _fetch_run_row(state_root, run.spawn_id)
    assert row.status == "succeeded"
    assert row.exit_code == 0
    report = (state_root / "spawns" / str(run.spawn_id) / "report.md").read_text(encoding="utf-8")
    assert "Actual work is done." in report


@pytest.mark.asyncio
async def test_execute_sets_cancelled_failure_reason(tmp_path: Path) -> None:
    run, state_root = _create_run(tmp_path, prompt="cancel")
    artifacts = LocalStore(root_dir=tmp_path / ".artifacts")

    script = tmp_path / "cancel.py"
    _write_script(
        script,
        """
        import time

        time.sleep(5.0)
        """,
    )
    adapter = ScriptHarnessAdapter(command=(sys.executable, str(script)))
    registry = HarnessRegistry()
    registry.register(adapter)

    task = asyncio.create_task(
        execute_with_finalization(
            run,
            plan=_build_plan(
                run,
                adapter.id,
                timeout_seconds=None,
                kill_grace_seconds=0.05,
                max_retries=0,
            ),
            repo_root=tmp_path,
            state_root=state_root,
            artifacts=artifacts,
            registry=registry,
            harness_id=adapter.id,
            cwd=tmp_path,
        )
    )
    await asyncio.sleep(0.05)
    task.cancel()
    exit_code = await task

    assert exit_code == 130
    row = _fetch_run_row(state_root, run.spawn_id)
    assert row.status == "cancelled"
    assert row.error == "cancelled"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("received_signal", "durable_report", "expected_status", "expected_exit_code"),
    [
        pytest.param(signal.SIGTERM, True, "succeeded", 0, id="forwarded-sigterm-with-report"),
        pytest.param(None, True, "succeeded", 0, id="raw-sigterm-with-report"),
        pytest.param(
            signal.SIGTERM,
            False,
            "cancelled",
            143,
            id="forwarded-sigterm-without-report",
        ),
    ],
)
async def test_execute_resolves_sigterm_after_report_regardless_of_received_signal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    received_signal: signal.Signals | None,
    durable_report: bool,
    expected_status: str,
    expected_exit_code: int,
) -> None:
    run, state_root = _create_run(tmp_path, prompt="sigterm lifecycle")
    artifacts = LocalStore(root_dir=tmp_path / ".artifacts")
    adapter = ScriptHarnessAdapter(command=("unused-command",))
    registry = HarnessRegistry()
    registry.register(adapter)

    async def fake_spawn_and_stream(
        *,
        spawn_id: SpawnId,
        output_log_path: Path,
        stderr_log_path: Path,
        report_watchdog_path: Path | None = None,
        **_: object,
    ) -> launch_runner.SpawnResult:
        _ = spawn_id
        if durable_report and report_watchdog_path is not None:
            report_watchdog_path.parent.mkdir(parents=True, exist_ok=True)
            report_watchdog_path.write_text("# Done\n\nWork completed.\n", encoding="utf-8")

        return launch_runner.SpawnResult(
            exit_code=143,
            raw_return_code=-signal.SIGTERM.value,
            timed_out=False,
            received_signal=received_signal,
            output_log_path=output_log_path,
            stderr_log_path=stderr_log_path,
            budget_breach=None,
            terminated_by_report_watchdog=False,
        )

    monkeypatch.setattr(launch_runner, "spawn_and_stream", fake_spawn_and_stream)

    exit_code = await execute_with_finalization(
        run,
        plan=_build_plan(
            run,
            adapter.id,
            max_retries=0,
        ),
        repo_root=tmp_path,
        state_root=state_root,
        artifacts=artifacts,
        registry=registry,
        harness_id=adapter.id,
        cwd=tmp_path,
    )

    assert exit_code == expected_exit_code
    row = _fetch_run_row(state_root, run.spawn_id)
    assert row.status == expected_status
    assert row.exit_code == expected_exit_code


@pytest.mark.asyncio
async def test_execute_with_finalization_starts_and_ticks_runner_heartbeat(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run, state_root = _create_run(tmp_path, prompt="heartbeat ticks")
    artifacts = LocalStore(root_dir=tmp_path / ".artifacts")
    adapter = ScriptHarnessAdapter(command=("unused-command",))
    registry = HarnessRegistry()
    registry.register(adapter)

    original_touch = launch_runner._touch_heartbeat_file
    touch_times: list[float] = []

    def _tracked_touch(state_root_arg: Path, spawn_id_arg: SpawnId) -> None:
        touch_times.append(asyncio.get_running_loop().time())
        original_touch(state_root_arg, spawn_id_arg)

    async def fake_spawn_and_stream(
        *,
        on_process_started,
        output_log_path: Path,
        stderr_log_path: Path,
        **_: object,
    ) -> launch_runner.SpawnResult:
        assert on_process_started is not None
        on_process_started(4242)
        await asyncio.sleep(0.07)
        return launch_runner.SpawnResult(
            exit_code=1,
            raw_return_code=1,
            timed_out=False,
            received_signal=None,
            output_log_path=output_log_path,
            stderr_log_path=stderr_log_path,
            budget_breach=None,
            terminated_by_report_watchdog=False,
        )

    monkeypatch.setattr(launch_runner, "_HEARTBEAT_INTERVAL_SECS", 0.02)
    monkeypatch.setattr(launch_runner, "_touch_heartbeat_file", _tracked_touch)
    monkeypatch.setattr(launch_runner, "spawn_and_stream", fake_spawn_and_stream)

    await execute_with_finalization(
        run,
        plan=_build_plan(run, adapter.id, max_retries=0),
        repo_root=tmp_path,
        state_root=state_root,
        artifacts=artifacts,
        registry=registry,
        harness_id=adapter.id,
        cwd=tmp_path,
    )

    assert len(touch_times) >= 2
    intervals = [later - earlier for earlier, later in pairwise(touch_times)]
    assert intervals
    assert max(intervals) <= 0.06
    assert (state_root / "spawns" / str(run.spawn_id) / "heartbeat").exists()


@pytest.mark.asyncio
async def test_execute_with_finalization_cancels_heartbeat_when_finalize_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run, state_root = _create_run(tmp_path, prompt="heartbeat cancel")
    artifacts = LocalStore(root_dir=tmp_path / ".artifacts")
    adapter = ScriptHarnessAdapter(command=("unused-command",))
    registry = HarnessRegistry()
    registry.register(adapter)

    touch_times: list[float] = []
    original_touch = launch_runner._touch_heartbeat_file

    def _tracked_touch(state_root_arg: Path, spawn_id_arg: SpawnId) -> None:
        touch_times.append(asyncio.get_running_loop().time())
        original_touch(state_root_arg, spawn_id_arg)

    async def fake_spawn_and_stream(
        *,
        on_process_started,
        output_log_path: Path,
        stderr_log_path: Path,
        **_: object,
    ) -> launch_runner.SpawnResult:
        assert on_process_started is not None
        on_process_started(5151)
        await asyncio.sleep(0.03)
        return launch_runner.SpawnResult(
            exit_code=1,
            raw_return_code=1,
            timed_out=False,
            received_signal=None,
            output_log_path=output_log_path,
            stderr_log_path=stderr_log_path,
            budget_breach=None,
            terminated_by_report_watchdog=False,
        )

    def _raising_finalize_spawn(*_args, **_kwargs) -> bool:
        raise RuntimeError("finalize boom")

    monkeypatch.setattr(launch_runner, "_HEARTBEAT_INTERVAL_SECS", 0.01)
    monkeypatch.setattr(launch_runner, "_touch_heartbeat_file", _tracked_touch)
    monkeypatch.setattr(launch_runner, "spawn_and_stream", fake_spawn_and_stream)
    monkeypatch.setattr(launch_runner.spawn_store, "finalize_spawn", _raising_finalize_spawn)

    with pytest.raises(RuntimeError, match="finalize boom"):
        await execute_with_finalization(
            run,
            plan=_build_plan(run, adapter.id, max_retries=0),
            repo_root=tmp_path,
            state_root=state_root,
            artifacts=artifacts,
            registry=registry,
            harness_id=adapter.id,
            cwd=tmp_path,
        )

    touched_count = len(touch_times)
    await asyncio.sleep(0.05)
    assert len(touch_times) == touched_count


@pytest.mark.asyncio
async def test_execute_with_finalization_cancels_heartbeat_when_finalize_raises_value_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run, state_root = _create_run(tmp_path, prompt="heartbeat cancel value error")
    artifacts = LocalStore(root_dir=tmp_path / ".artifacts")
    adapter = ScriptHarnessAdapter(command=("unused-command",))
    registry = HarnessRegistry()
    registry.register(adapter)

    touch_times: list[float] = []
    original_touch = launch_runner._touch_heartbeat_file

    def _tracked_touch(state_root_arg: Path, spawn_id_arg: SpawnId) -> None:
        touch_times.append(asyncio.get_running_loop().time())
        original_touch(state_root_arg, spawn_id_arg)

    async def fake_spawn_and_stream(
        *,
        on_process_started,
        output_log_path: Path,
        stderr_log_path: Path,
        **_: object,
    ) -> launch_runner.SpawnResult:
        assert on_process_started is not None
        on_process_started(6161)
        await asyncio.sleep(0.03)
        return launch_runner.SpawnResult(
            exit_code=1,
            raw_return_code=1,
            timed_out=False,
            received_signal=None,
            output_log_path=output_log_path,
            stderr_log_path=stderr_log_path,
            budget_breach=None,
            terminated_by_report_watchdog=False,
        )

    def _raising_finalize_spawn(*_args, **_kwargs) -> bool:
        raise ValueError("finalize value error")

    monkeypatch.setattr(launch_runner, "_HEARTBEAT_INTERVAL_SECS", 0.01)
    monkeypatch.setattr(launch_runner, "_touch_heartbeat_file", _tracked_touch)
    monkeypatch.setattr(launch_runner, "spawn_and_stream", fake_spawn_and_stream)
    monkeypatch.setattr(launch_runner.spawn_store, "finalize_spawn", _raising_finalize_spawn)

    with pytest.raises(ValueError, match="finalize value error"):
        await execute_with_finalization(
            run,
            plan=_build_plan(run, adapter.id, max_retries=0),
            repo_root=tmp_path,
            state_root=state_root,
            artifacts=artifacts,
            registry=registry,
            harness_id=adapter.id,
            cwd=tmp_path,
        )

    touched_count = len(touch_times)
    await asyncio.sleep(0.05)
    assert len(touch_times) == touched_count
