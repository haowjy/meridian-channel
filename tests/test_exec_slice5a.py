"""Slice 5a execution/finalization behavior tests."""

from __future__ import annotations

import sqlite3
import sys
import textwrap
from pathlib import Path

import pytest

from meridian.lib.adapters.sqlite import StateDB
from meridian.lib.domain import RunCreateParams, TokenUsage
from meridian.lib.exec.spawn import execute_with_finalization
from meridian.lib.harness._common import (
    extract_session_id_from_artifacts,
    extract_usage_from_artifacts,
)
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
from meridian.lib.state.artifact_store import LocalStore
from meridian.lib.types import HarnessId, ModelId, RunId


class ScriptHarnessAdapter:
    def __init__(self, *, command: tuple[str, ...]) -> None:
        self._command = command

    @property
    def id(self) -> HarnessId:
        return HarnessId("slice5-script")

    @property
    def capabilities(self) -> HarnessCapabilities:
        return HarnessCapabilities()

    def build_command(self, run: RunParams, perms: PermissionResolver) -> list[str]:
        return [*self._command, *perms.resolve_flags(self.id), *run.extra_args]

    def parse_stream_event(self, line: str) -> StreamEvent | None:
        _ = line
        return None

    def extract_usage(self, artifacts: HarnessArtifactStore, run_id: RunId) -> TokenUsage:
        return extract_usage_from_artifacts(artifacts, run_id)

    def extract_session_id(self, artifacts: HarnessArtifactStore, run_id: RunId) -> str | None:
        return extract_session_id_from_artifacts(artifacts, run_id)


def _fetch_run_row(state: StateDB, run_id: RunId) -> sqlite3.Row:
    conn = sqlite3.connect(state.paths.db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (str(run_id),)).fetchone()
    finally:
        conn.close()
    assert row is not None
    return row


def _write_script(path: Path, source: str) -> None:
    path.write_text(textwrap.dedent(source), encoding="utf-8")


@pytest.mark.asyncio
async def test_execute_retries_retryable_errors_up_to_max(tmp_path: Path) -> None:
    state = StateDB(tmp_path)
    run = state.create_run(RunCreateParams(prompt="retry me", model=ModelId("gpt-5.3-codex")))
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
        state=state,
        artifacts=artifacts,
        registry=registry,
        harness_id=adapter.id,
        cwd=tmp_path,
        max_retries=3,
        retry_backoff_seconds=0.0,
    )

    assert exit_code == 1
    assert counter.read_text(encoding="utf-8") == "4"
    row = _fetch_run_row(state, run.run_id)
    assert row["status"] == "failed"
    assert row["failure_reason"] == "agent_error"


@pytest.mark.asyncio
async def test_execute_does_not_retry_unrecoverable_errors(tmp_path: Path) -> None:
    state = StateDB(tmp_path)
    run = state.create_run(RunCreateParams(prompt="fail once", model=ModelId("gpt-5.3-codex")))
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
        state=state,
        artifacts=artifacts,
        registry=registry,
        harness_id=adapter.id,
        cwd=tmp_path,
        max_retries=3,
        retry_backoff_seconds=0.0,
    )

    assert exit_code == 1
    assert counter.read_text(encoding="utf-8") == "1"


@pytest.mark.asyncio
async def test_execute_marks_empty_success_output_as_failed(tmp_path: Path) -> None:
    state = StateDB(tmp_path)
    run = state.create_run(RunCreateParams(prompt="empty", model=ModelId("gpt-5.3-codex")))
    artifacts = LocalStore(root_dir=tmp_path / ".artifacts")

    script = tmp_path / "empty-success.py"
    _write_script(
        script,
        """
        raise SystemExit(0)
        """,
    )
    adapter = ScriptHarnessAdapter(command=(sys.executable, str(script)))
    registry = HarnessRegistry()
    registry.register(adapter)

    exit_code = await execute_with_finalization(
        run,
        state=state,
        artifacts=artifacts,
        registry=registry,
        harness_id=adapter.id,
        cwd=tmp_path,
        max_retries=3,
        retry_backoff_seconds=0.0,
    )

    assert exit_code == 1
    row = _fetch_run_row(state, run.run_id)
    assert row["status"] == "failed"
    assert row["failure_reason"] == "empty_output"


@pytest.mark.asyncio
async def test_retry_does_not_reuse_stale_fallback_report(tmp_path: Path) -> None:
    state = StateDB(tmp_path)
    run = state.create_run(
        RunCreateParams(prompt="retry stale fallback", model=ModelId("gpt-5.3-codex"))
    )
    artifacts = LocalStore(root_dir=tmp_path / ".artifacts")

    counter = tmp_path / "attempt-count.txt"
    script = tmp_path / "retry-stale-fallback.py"
    _write_script(
        script,
        """
        from pathlib import Path
        import sys

        counter = Path(sys.argv[1])
        if counter.exists():
            attempt = int(counter.read_text(encoding="utf-8"))
        else:
            attempt = 0
        counter.write_text(str(attempt + 1), encoding="utf-8")

        if attempt == 0:
            print('{"role":"assistant","content":"first attempt fallback report"}', flush=True)
            print("network error: timeout", file=sys.stderr, flush=True)
            raise SystemExit(1)

        # Successful exit with no output should still fail finalization as empty output.
        raise SystemExit(0)
        """,
    )

    adapter = ScriptHarnessAdapter(command=(sys.executable, str(script), str(counter)))
    registry = HarnessRegistry()
    registry.register(adapter)

    exit_code = await execute_with_finalization(
        run,
        state=state,
        artifacts=artifacts,
        registry=registry,
        harness_id=adapter.id,
        cwd=tmp_path,
        max_retries=1,
        retry_backoff_seconds=0.0,
    )

    assert exit_code == 1
    row = _fetch_run_row(state, run.run_id)
    assert row["status"] == "failed"
    assert row["failure_reason"] == "empty_output"
    assert row["report_path"] is None


@pytest.mark.asyncio
async def test_finalize_row_enriched_with_usage_cost_session_and_files(
    package_root: Path,
    tmp_path: Path,
) -> None:
    state = StateDB(tmp_path)
    run = state.create_run(RunCreateParams(prompt="enrich", model=ModelId("gpt-5.3-codex")))
    artifacts = LocalStore(root_dir=tmp_path / ".artifacts")

    stream_fixture = tmp_path / "slice5-stream.jsonl"
    stream_fixture.write_text(
        (
            '{"role":"assistant","content":"Edited src/story/ch1.md","session_id":"sess-7",'
            '"files_touched":["src/story/ch1.md","_docs/plans/plan.md"]}\n'
            '{"role":"assistant","content":"Final summary."}\n'
        ),
        encoding="utf-8",
    )

    adapter = ScriptHarnessAdapter(
        command=(
            sys.executable,
            str(package_root / "tests" / "mock_harness.py"),
            "--tokens",
            '{"input_tokens":22,"output_tokens":7,"total_cost_usd":0.014}',
            "--stdout-file",
            str(stream_fixture),
        )
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
        max_retries=0,
    )

    assert exit_code == 0
    row = _fetch_run_row(state, run.run_id)
    assert row["status"] == "succeeded"
    assert row["input_tokens"] == 22
    assert row["output_tokens"] == 7
    assert row["total_cost_usd"] == pytest.approx(0.014)
    assert row["harness_session_id"] == "sess-7"
    assert row["files_touched_count"] == 2

    report_path = tmp_path / str(row["report_path"])
    assert report_path.exists()
    assert "Final summary." in report_path.read_text(encoding="utf-8")
