"""State-layer tests for Slice 1 acceptance criteria."""

from __future__ import annotations

import dataclasses
import json
import multiprocessing
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from meridian.lib.adapters.sqlite import (
    RunFinalizeRow,
    RunStartRow,
    SQLiteContextStore,
    SQLiteRunStore,
    SQLiteRunStoreSync,
    SQLiteWorkspaceStore,
    StateDB,
)
from meridian.lib.domain import (
    ArtifactRecord,
    PinnedFile,
    Run,
    RunCreateParams,
    RunEdge,
    RunEnrichment,
    RunFilters,
    Span,
    TokenUsage,
    WorkflowEvent,
    Workspace,
    WorkspaceCreateParams,
)
from meridian.lib.state.artifact_store import InMemoryStore, LocalStore, make_artifact_key
from meridian.lib.state.db import get_busy_timeout, get_journal_mode, open_connection
from meridian.lib.state.id_gen import next_run_id
from meridian.lib.state.schema import (
    LATEST_SCHEMA_VERSION,
    REQUIRED_TABLES,
    get_schema_version,
    list_tables,
)
from meridian.lib.types import HarnessId, ModelId, RunId, SpanId, TraceId


def _write_start_and_finalize(repo_root: str, idx: int) -> None:
    root = Path(repo_root)
    state = StateDB(root)
    run_id = RunId(f"rlock{idx}")
    log_dir = root / ".meridian" / "runs" / str(run_id)

    state.append_start_row(
        RunStartRow(
            run_id=run_id,
            model=ModelId("gpt-5.3-codex"),
            harness=HarnessId("codex"),
            cwd=root,
            log_dir=log_dir,
            session_id=str(run_id),
        )
    )
    state.append_finalize_row(
        run_id,
        RunFinalizeRow(
            exit_code=0,
            duration_seconds=0.1,
            output_log=log_dir / "output.jsonl",
            report_path=log_dir / "report.md",
            harness_session_id="hsess",
            input_tokens=123,
            output_tokens=45,
        ),
    )


def test_schema_bootstrap_and_db_pragmas(tmp_path: Path) -> None:
    state = StateDB(tmp_path)
    assert state.paths.db_path.exists()

    conn = open_connection(state.paths.db_path)
    try:
        assert get_journal_mode(conn) == "wal"
        assert get_busy_timeout(conn) == 5000
        assert REQUIRED_TABLES.issubset(list_tables(conn))
        assert get_schema_version(conn) == LATEST_SCHEMA_VERSION
    finally:
        conn.close()


def test_run_and_workspace_crud_with_counter_ids(tmp_path: Path) -> None:
    state = StateDB(tmp_path)

    workspace = state.create_workspace(WorkspaceCreateParams(name="writer-room"))
    assert str(workspace.workspace_id) == "w1"

    standalone_run = state.create_run(
        RunCreateParams(prompt="standalone", model=ModelId("claude-opus-4-6"))
    )
    ws_run_1 = state.create_run(
        RunCreateParams(
            prompt="workspace-1",
            model=ModelId("gpt-5.3-codex"),
            workspace_id=workspace.workspace_id,
        )
    )
    ws_run_2 = state.create_run(
        RunCreateParams(
            prompt="workspace-2",
            model=ModelId("gpt-5.3-codex"),
            workspace_id=workspace.workspace_id,
        )
    )

    assert str(standalone_run.run_id) == "r1"
    assert str(ws_run_1.run_id) == "w1/r1"
    assert str(ws_run_2.run_id) == "w1/r2"

    loaded = state.get_run(ws_run_1.run_id)
    assert loaded is not None
    assert loaded.prompt == "workspace-1"

    state.update_run_status(ws_run_1.run_id, "running")
    state.enrich_run(
        ws_run_1.run_id,
        RunEnrichment(
            usage=TokenUsage(input_tokens=10, output_tokens=20),
            report_path=tmp_path / "report.md",
        ),
    )

    summaries = state.list_runs(RunFilters(workspace_id=workspace.workspace_id))
    assert {str(summary.run_id) for summary in summaries} == {"w1/r1", "w1/r2"}


def test_append_start_finalize_dual_write_and_relative_paths(tmp_path: Path) -> None:
    state = StateDB(tmp_path)
    run = state.create_run(RunCreateParams(prompt="hello", model=ModelId("gpt-5.3-codex")))

    run_dir = tmp_path / ".meridian" / "runs" / str(run.run_id)
    started_at = datetime(2026, 2, 25, 0, 0, 0, tzinfo=UTC)
    finished_at = datetime(2026, 2, 25, 0, 0, 4, tzinfo=UTC)

    state.append_start_row(
        RunStartRow(
            run_id=run.run_id,
            model=ModelId("gpt-5.3-codex"),
            harness=HarnessId("codex"),
            cwd=tmp_path,
            log_dir=run_dir,
            session_id="session-1",
            started_at=started_at,
        )
    )
    state.append_finalize_row(
        run.run_id,
        RunFinalizeRow(
            exit_code=0,
            duration_seconds=4.0,
            finished_at=finished_at,
            output_log=run_dir / "output.jsonl",
            report_path=run_dir / "report.md",
            input_tokens=222,
            output_tokens=111,
        ),
    )

    rows = state.read_jsonl_rows()
    assert len(rows) == 2
    assert rows[0]["status"] == "running"
    assert rows[1]["status"] == "succeeded"

    conn = open_connection(state.paths.db_path)
    try:
        row = conn.execute(
            "SELECT status, cwd, log_dir, output_log, report_path FROM runs WHERE id = ?",
            (str(run.run_id),),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["status"] == "succeeded"
    for key in ("cwd", "log_dir", "output_log", "report_path"):
        value = str(row[key])
        assert not Path(value).is_absolute()


def test_events_spans_edges_and_artifacts(tmp_path: Path) -> None:
    state = StateDB(tmp_path)
    workspace = state.create_workspace(WorkspaceCreateParams(name="events"))
    run = state.create_run(
        RunCreateParams(
            prompt="edge target",
            model=ModelId("gpt-5.3-codex"),
            workspace_id=workspace.workspace_id,
        )
    )

    event = state.append_workflow_event(
        workspace_id=workspace.workspace_id,
        event_type="TaskScheduled",
        payload={"step": "research"},
        run_id=run.run_id,
    )
    assert event.event_type == "TaskScheduled"

    span = Span(
        span_id=SpanId("span-1"),
        trace_id=TraceId(str(workspace.workspace_id)),
        parent_id=None,
        name="run",
        kind="workflow",
        started_at=datetime.now(UTC),
        attributes={"k": "v"},
    )
    state.add_span(span)
    state.finish_span(
        SpanId("span-1"),
        status="ok",
        attributes={"input_tokens": 123},
    )

    child_run = state.create_run(
        RunCreateParams(
            prompt="child",
            model=ModelId("claude-haiku-4-5"),
            workspace_id=workspace.workspace_id,
        )
    )
    state.add_run_edge(
        RunEdge(
            source_run_id=run.run_id,
            target_run_id=child_run.run_id,
            edge_type="parent",
        )
    )

    artifact = ArtifactRecord(
        run_id=run.run_id,
        key=make_artifact_key(run.run_id, "report.md"),
        path=tmp_path / ".meridian" / "runs" / "report.md",
        size=42,
    )
    state.upsert_artifact(artifact)

    events = state.list_workflow_events(workspace.workspace_id)
    assert len(events) == 1
    assert events[0].payload["step"] == "research"

    spans = state.list_spans(TraceId(str(workspace.workspace_id)))
    assert len(spans) == 1
    assert spans[0].ended_at is not None

    artifacts = state.list_artifact_records(run.run_id)
    assert len(artifacts) == 1
    assert artifacts[0].path.is_absolute()


def test_context_pinning_stores_relative_and_reads_absolute(tmp_path: Path) -> None:
    state = StateDB(tmp_path)
    workspace = state.create_workspace(WorkspaceCreateParams(name="ctx"))
    file_path = tmp_path / "notes" / "summary.md"

    state.pin_file(workspace.workspace_id, file_path.as_posix())
    pinned = state.list_pinned_files(workspace.workspace_id)
    assert pinned == [
        PinnedFile(
            workspace_id=workspace.workspace_id,
            file_path=file_path.as_posix(),
        )
    ]

    conn = open_connection(state.paths.db_path)
    try:
        row = conn.execute(
            "SELECT file_path FROM pinned_files WHERE workspace_id = ?",
            (str(workspace.workspace_id),),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["file_path"] == "notes/summary.md"


def test_locking_contention_writes_clean_jsonl_and_sqlite(tmp_path: Path) -> None:
    state = StateDB(tmp_path)
    process_count = 8

    ctx = multiprocessing.get_context("spawn")
    procs = [
        ctx.Process(target=_write_start_and_finalize, args=(tmp_path.as_posix(), idx))
        for idx in range(process_count)
    ]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join(timeout=20)
        assert proc.exitcode == 0

    rows = state.read_jsonl_rows()
    assert len(rows) == process_count * 2

    # Every line must remain parseable JSON under concurrent append pressure.
    with state.paths.jsonl_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            json.loads(line)

    conn = open_connection(state.paths.db_path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM runs WHERE status = 'succeeded'").fetchone()
    finally:
        conn.close()

    assert count is not None
    assert int(count[0]) == process_count


def test_jsonl_round_trip_skips_corrupt_lines(tmp_path: Path) -> None:
    state = StateDB(tmp_path)
    state.paths.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    state.paths.jsonl_path.write_text(
        '{"run_id":"r1","status":"running"}\nnot-json\n{"run_id":"r1","status":"succeeded"}\n',
        encoding="utf-8",
    )

    rows = state.read_jsonl_rows()
    assert rows == [
        {"run_id": "r1", "status": "running"},
        {"run_id": "r1", "status": "succeeded"},
    ]


def test_artifact_store_local_and_memory(tmp_path: Path) -> None:
    key = make_artifact_key(RunId("r1"), "output.jsonl")

    local = LocalStore(root_dir=tmp_path / "artifacts")
    local.put(key, b"hello")
    assert local.exists(key)
    assert local.get(key) == b"hello"
    assert local.list_artifacts("r1") == [key]
    local.delete(key)
    assert not local.exists(key)

    memory = InMemoryStore()
    memory.put(key, b"world")
    assert memory.exists(key)
    assert memory.get(key) == b"world"
    assert memory.list_artifacts("r1") == [key]
    memory.delete(key)
    assert not memory.exists(key)


@pytest.mark.asyncio
async def test_async_protocol_adapters_and_domain_frozen(tmp_path: Path) -> None:
    state = StateDB(tmp_path)
    sync_store = SQLiteRunStoreSync(state)
    run_store = SQLiteRunStore(sync_store)
    workspace_store = SQLiteWorkspaceStore(state)
    context_store = SQLiteContextStore(state)

    workspace = await workspace_store.create(WorkspaceCreateParams(name="async"))
    run = await run_store.create(
        RunCreateParams(
            prompt="async run", model=ModelId("gpt-5.3-codex"), workspace_id=workspace.workspace_id
        )
    )
    loaded = await run_store.get(run.run_id)
    assert loaded is not None

    await context_store.pin(workspace.workspace_id, (tmp_path / "context.md").as_posix())
    pinned = await context_store.list_pinned(workspace.workspace_id)
    assert len(pinned) == 1

    for cls in (Run, Workspace, PinnedFile, WorkflowEvent, Span):
        assert dataclasses.is_dataclass(cls)
        assert cls.__dataclass_params__.frozen


def test_workspace_and_global_run_id_generation_uses_counters(tmp_path: Path) -> None:
    state = StateDB(tmp_path)
    workspace = state.create_workspace(WorkspaceCreateParams(name="idgen"))

    conn = open_connection(state.paths.db_path)
    try:
        with conn:
            standalone_1 = next_run_id(conn, None)
            standalone_2 = next_run_id(conn, None)
            workspace_1 = next_run_id(conn, workspace.workspace_id)
            workspace_2 = next_run_id(conn, workspace.workspace_id)
    finally:
        conn.close()

    assert str(standalone_1.full_id) == "r1"
    assert str(standalone_2.full_id) == "r2"
    assert str(workspace_1.full_id) == f"{workspace.workspace_id}/r1"
    assert str(workspace_2.full_id) == f"{workspace.workspace_id}/r2"


def test_create_run_raises_on_duplicate_generated_id(tmp_path: Path) -> None:
    state = StateDB(tmp_path)
    state.create_run(RunCreateParams(prompt="first", model=ModelId("gpt-5.3-codex")))

    conn = open_connection(state.paths.db_path)
    try:
        with conn:
            conn.execute(
                "UPDATE schema_info SET value = '0' WHERE key = 'counter:run:global'",
            )
    finally:
        conn.close()

    with pytest.raises(sqlite3.IntegrityError):
        state.create_run(RunCreateParams(prompt="duplicate", model=ModelId("gpt-5.3-codex")))
