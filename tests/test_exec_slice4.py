"""Slice 4 execution engine tests."""

from __future__ import annotations

import asyncio
import os
import signal
import sqlite3
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import cast

import pytest

from meridian.lib.adapters.sqlite import RunFinalizeRow, StateDB
from meridian.lib.domain import RunCreateParams, TokenUsage
from meridian.lib.exec.signals import SignalForwarder, map_process_exit_code, signal_to_exit_code
from meridian.lib.exec.spawn import SafeDefaultPermissionResolver, execute_with_finalization
from meridian.lib.harness.adapter import (
    ArtifactStore as HarnessArtifactStore,
)
from meridian.lib.harness.adapter import (
    HarnessCapabilities,
    PermissionResolver,
    RunParams,
    StreamEvent,
)
from meridian.lib.harness.registry import HarnessRegistry
from meridian.lib.state.artifact_store import LocalStore, make_artifact_key
from meridian.lib.types import HarnessId, ModelId, RunId


class RecordingPermissionResolver(PermissionResolver):
    def __init__(self, *, flags: tuple[str, ...] = ()) -> None:
        self.flags = flags
        self.seen_harness_ids: list[HarnessId] = []

    def resolve_flags(self, harness_id: HarnessId) -> list[str]:
        self.seen_harness_ids.append(harness_id)
        return list(self.flags)


class MockHarnessAdapter:
    """Test harness adapter that shells out to tests/mock_harness.py."""

    def __init__(
        self,
        *,
        script: Path,
        base_args: tuple[str, ...] = (),
        command_override: tuple[str, ...] | None = None,
    ) -> None:
        self._script = script
        self._base_args = base_args
        self._command_override = command_override
        self.build_calls = 0
        self.last_params: RunParams | None = None

    @property
    def id(self) -> HarnessId:
        return HarnessId("mock")

    @property
    def capabilities(self) -> HarnessCapabilities:
        return HarnessCapabilities()

    def build_command(self, run: RunParams, perms: PermissionResolver) -> list[str]:
        self.build_calls += 1
        self.last_params = run

        if self._command_override is not None:
            command = [*self._command_override]
        else:
            command = [
                sys.executable,
                str(self._script),
                *self._base_args,
            ]
        command.extend(perms.resolve_flags(self.id))
        command.extend(run.extra_args)
        return command

    def parse_stream_event(self, line: str) -> StreamEvent | None:
        _ = line
        return None

    def extract_usage(self, artifacts: HarnessArtifactStore, run_id: RunId) -> TokenUsage:
        _ = (artifacts, run_id)
        return TokenUsage()

    def extract_session_id(self, artifacts: HarnessArtifactStore, run_id: RunId) -> str | None:
        key = make_artifact_key(run_id, "session_id.txt")
        if artifacts.exists(key):
            return artifacts.get(key).decode("utf-8").strip()
        return None


def _fetch_run_row(state: StateDB, run_id: RunId) -> sqlite3.Row:
    conn = sqlite3.connect(state.paths.db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (str(run_id),)).fetchone()
    finally:
        conn.close()
    assert row is not None
    return row


@pytest.mark.asyncio
async def test_execute_with_finalization_streams_and_captures(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    package_root: Path,
    tmp_path: Path,
) -> None:
    import meridian.lib.exec.spawn as spawn_module

    state = StateDB(tmp_path)
    run = state.create_run(RunCreateParams(prompt="stream", model=ModelId("gpt-5.3-codex")))
    artifacts = LocalStore(root_dir=tmp_path / ".artifacts")
    fixture = package_root / "tests" / "fixtures" / "partial.jsonl"
    adapter = MockHarnessAdapter(
        script=package_root / "tests" / "mock_harness.py",
        base_args=(
            "--stdout-file",
            str(fixture),
            "--stderr",
            "slice4 warning",
            "--stream-delay",
            "0.01",
        ),
    )
    registry = HarnessRegistry()
    registry.register(adapter)
    perms = RecordingPermissionResolver()

    called = False
    original = spawn_module.asyncio.create_subprocess_exec

    async def wrapped_create_subprocess_exec(*args: object, **kwargs: object):
        nonlocal called
        called = True
        return await original(*args, **kwargs)

    monkeypatch.setattr(
        spawn_module.asyncio,
        "create_subprocess_exec",
        wrapped_create_subprocess_exec,
    )

    exit_code = await execute_with_finalization(
        run,
        state=state,
        artifacts=artifacts,
        registry=registry,
        permission_resolver=perms,
        harness_id=adapter.id,
        cwd=tmp_path,
        timeout_seconds=5.0,
    )

    assert called is True
    assert exit_code == 0
    assert adapter.build_calls == 1
    assert adapter.last_params is not None
    assert perms.seen_harness_ids == [HarnessId("mock")]

    row = _fetch_run_row(state, run.run_id)
    assert row["status"] == "succeeded"
    assert row["exit_code"] == 0

    output_key = make_artifact_key(run.run_id, "output.jsonl")
    stderr_key = make_artifact_key(run.run_id, "stderr.log")
    assert artifacts.exists(output_key)
    assert artifacts.exists(stderr_key)

    output_text = artifacts.get(output_key).decode("utf-8")
    assert '{"line": 1}' in output_text
    assert '{"line": 3}' in output_text
    stderr_text = artifacts.get(stderr_key).decode("utf-8")
    assert "slice4 warning" in stderr_text

    captured = capsys.readouterr()
    assert "slice4 warning" in captured.err


@pytest.mark.asyncio
async def test_timeout_kills_child_and_finalizes_row(package_root: Path, tmp_path: Path) -> None:
    state = StateDB(tmp_path)
    run = state.create_run(RunCreateParams(prompt="hang", model=ModelId("gpt-5.3-codex")))
    artifacts = LocalStore(root_dir=tmp_path / ".artifacts")
    adapter = MockHarnessAdapter(
        script=package_root / "tests" / "mock_harness.py",
        base_args=("--hang",),
    )
    registry = HarnessRegistry()
    registry.register(adapter)

    exit_code = await execute_with_finalization(
        run,
        state=state,
        artifacts=artifacts,
        registry=registry,
        harness_id=adapter.id,
        cwd=tmp_path,
        timeout_seconds=0.2,
        kill_grace_seconds=0.1,
    )

    assert exit_code == 3
    row = _fetch_run_row(state, run.run_id)
    assert row["status"] == "failed"
    assert row["exit_code"] == 3
    assert row["failure_reason"] == "timeout"
    assert row["finished_at"] is not None


@pytest.mark.asyncio
async def test_infra_failure_still_writes_finalize_row(tmp_path: Path) -> None:
    state = StateDB(tmp_path)
    run = state.create_run(RunCreateParams(prompt="boom", model=ModelId("gpt-5.3-codex")))
    artifacts = LocalStore(root_dir=tmp_path / ".artifacts")
    adapter = MockHarnessAdapter(
        script=tmp_path / "unused.py",
        command_override=("definitely-missing-binary-for-slice4",),
    )
    registry = HarnessRegistry()
    registry.register(adapter)

    exit_code = await execute_with_finalization(
        run,
        state=state,
        artifacts=artifacts,
        registry=registry,
        harness_id=adapter.id,
        cwd=tmp_path,
        timeout_seconds=1.0,
    )

    assert exit_code == 2
    row = _fetch_run_row(state, run.run_id)
    assert row["status"] == "failed"
    assert row["exit_code"] == 2
    assert row["failure_reason"] == "infra_error"
    assert row["finished_at"] is not None


@pytest.mark.asyncio
async def test_execute_with_finalization_ignores_sigterm_during_finalize_write(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import meridian.lib.exec.spawn as spawn_module

    state = StateDB(tmp_path)
    run = state.create_run(RunCreateParams(prompt="boom", model=ModelId("gpt-5.3-codex")))
    artifacts = LocalStore(root_dir=tmp_path / ".artifacts")
    adapter = MockHarnessAdapter(
        script=tmp_path / "unused.py",
        command_override=("definitely-missing-binary-for-slice4",),
    )
    registry = HarnessRegistry()
    registry.register(adapter)

    current_sigterm_handler: object = signal.SIG_DFL
    transitioned_handlers: list[object] = []
    original_signal = spawn_module.signal.signal

    def fake_signal(raw_signum: int, handler: object) -> object:
        nonlocal current_sigterm_handler
        signum = signal.Signals(raw_signum)
        if signum != signal.SIGTERM:
            return original_signal(raw_signum, handler)
        previous = current_sigterm_handler
        current_sigterm_handler = handler
        transitioned_handlers.append(handler)
        return previous

    monkeypatch.setattr(spawn_module.signal, "signal", fake_signal)

    finalize_called = False
    original_append_finalize_row = state.append_finalize_row

    def wrapped_append_finalize_row(run_id: RunId, row: RunFinalizeRow) -> None:
        nonlocal finalize_called
        finalize_called = True
        assert current_sigterm_handler == signal.SIG_IGN
        original_append_finalize_row(run_id, row)

    monkeypatch.setattr(state, "append_finalize_row", wrapped_append_finalize_row)

    exit_code = await execute_with_finalization(
        run,
        state=state,
        artifacts=artifacts,
        registry=registry,
        harness_id=adapter.id,
        cwd=tmp_path,
        timeout_seconds=1.0,
    )

    assert exit_code == 2
    assert finalize_called is True
    assert transitioned_handlers
    assert transitioned_handlers[0] == signal.SIG_IGN
    assert transitioned_handlers[-1] != signal.SIG_IGN


def test_signal_forwarder_forwards_sigint_and_sigterm() -> None:
    class FakeProcess:
        def __init__(self) -> None:
            self.returncode: int | None = None
            self.sent_signals: list[signal.Signals] = []
            self.killed = False

        def send_signal(self, signum: int) -> None:
            self.sent_signals.append(signal.Signals(signum))

        def kill(self) -> None:
            self.killed = True
            self.returncode = -9

    fake = FakeProcess()
    forwarder = SignalForwarder(cast("asyncio.subprocess.Process", fake))
    forwarder.forward_signal(signal.SIGINT)
    forwarder.forward_signal(signal.SIGTERM)

    assert fake.sent_signals == [signal.SIGINT, signal.SIGTERM]
    assert fake.killed is True
    assert forwarder.received_signal == signal.SIGTERM

    assert signal_to_exit_code(signal.SIGINT) == 130
    assert signal_to_exit_code(signal.SIGTERM) == 143
    assert map_process_exit_code(raw_return_code=0, received_signal=signal.SIGTERM) == 143


def test_safe_default_permission_resolver_returns_no_flags() -> None:
    resolver = SafeDefaultPermissionResolver()
    assert resolver.resolve_flags(HarnessId("codex")) == []


def test_kill_running_parent_process_still_finalizes_run(
    package_root: Path,
    tmp_path: Path,
) -> None:
    worker_path = tmp_path / "slice4_worker.py"
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    mock_harness = package_root / "tests" / "mock_harness.py"

    worker_path.write_text(
        textwrap.dedent(
            f"""
            from __future__ import annotations

            import asyncio
            import sys
            from pathlib import Path

            from meridian.lib.adapters.sqlite import StateDB
            from meridian.lib.domain import RunCreateParams, TokenUsage
            from meridian.lib.exec.spawn import execute_with_finalization
            from meridian.lib.harness.adapter import (
                ArtifactStore,
                HarnessCapabilities,
                PermissionResolver,
                RunParams,
                StreamEvent,
            )
            from meridian.lib.harness.registry import HarnessRegistry
            from meridian.lib.state.artifact_store import LocalStore
            from meridian.lib.types import HarnessId, ModelId, RunId


            class WorkerAdapter:
                @property
                def id(self) -> HarnessId:
                    return HarnessId("worker-mock")

                @property
                def capabilities(self) -> HarnessCapabilities:
                    return HarnessCapabilities()

                def build_command(self, run: RunParams, perms: PermissionResolver) -> list[str]:
                    _ = run
                    return [
                        sys.executable,
                        "{mock_harness.as_posix()}",
                        "--hang",
                        *perms.resolve_flags(self.id),
                    ]

                def parse_stream_event(self, line: str) -> StreamEvent | None:
                    _ = line
                    return None

                def extract_usage(self, artifacts: ArtifactStore, run_id: RunId) -> TokenUsage:
                    _ = (artifacts, run_id)
                    return TokenUsage()

                def extract_session_id(self, artifacts: ArtifactStore, run_id: RunId) -> str | None:
                    _ = (artifacts, run_id)
                    return None


            async def main() -> int:
                state = StateDB(Path("{repo_root.as_posix()}"))
                run = state.create_run(
                    RunCreateParams(prompt="hang", model=ModelId("gpt-5.3-codex"))
                )
                artifacts = LocalStore(
                    root_dir=Path("{(tmp_path / '.artifacts-worker').as_posix()}")
                )
                registry = HarnessRegistry()
                registry.register(WorkerAdapter())
                return await execute_with_finalization(
                    run,
                    state=state,
                    artifacts=artifacts,
                    registry=registry,
                    harness_id=HarnessId("worker-mock"),
                    cwd=Path("{repo_root.as_posix()}"),
                    timeout_seconds=30.0,
                )


            raise SystemExit(asyncio.run(main()))
            """
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    root = str(package_root / "src")
    env["PYTHONPATH"] = root if not existing else f"{root}:{existing}"

    proc = subprocess.Popen(
        [sys.executable, str(worker_path)],
        cwd=package_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        db_path = repo_root / ".meridian" / "index" / "runs.db"
        deadline = time.time() + 10.0
        saw_running = False
        while time.time() < deadline:
            if db_path.exists():
                conn = sqlite3.connect(db_path)
                try:
                    row = conn.execute("SELECT status FROM runs WHERE id = 'r1'").fetchone()
                except sqlite3.OperationalError:
                    row = None
                finally:
                    conn.close()
                if row is not None and row[0] == "running":
                    saw_running = True
                    break
            time.sleep(0.05)

        assert saw_running is True
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=20)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)

    conn = sqlite3.connect(repo_root / ".meridian" / "index" / "runs.db")
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT status, exit_code FROM runs WHERE id = 'r1'").fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["status"] == "failed"
    assert row["exit_code"] == 143
