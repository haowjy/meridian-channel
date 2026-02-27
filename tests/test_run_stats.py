"""run.stats aggregate and filter behavior."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from meridian.lib.ops.run import RunStatsInput, run_stats_sync
from meridian.lib.state.db import resolve_state_paths
from meridian.lib.state.schema import apply_migrations


def _insert_run(
    db_path: Path,
    *,
    run_id: str,
    local_id: str,
    model: str,
    status: str,
    workspace_id: str | None = None,
    duration_secs: float | None = None,
    total_cost_usd: float | None = None,
    harness_session_id: str | None = None,
) -> None:
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO runs(
                    id,
                    workspace_id,
                    local_id,
                    model,
                    harness,
                    status,
                    started_at,
                    log_dir,
                    duration_secs,
                    total_cost_usd,
                    harness_session_id
                )
                VALUES(?, ?, ?, ?, 'codex', ?, '2026-02-27T00:00:00Z', '.', ?, ?, ?)
                """,
                (
                    run_id,
                    workspace_id,
                    local_id,
                    model,
                    status,
                    duration_secs,
                    total_cost_usd,
                    harness_session_id,
                ),
            )
    finally:
        conn.close()


def test_run_stats_sync_aggregates_all_runs(tmp_path: Path) -> None:
    db_path = resolve_state_paths(tmp_path).db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        apply_migrations(conn)
    finally:
        conn.close()

    _insert_run(
        db_path,
        run_id="r1",
        local_id="r1",
        model="gpt-5.3-codex",
        status="succeeded",
        workspace_id="w1",
        duration_secs=2.5,
        total_cost_usd=0.25,
        harness_session_id="sess-a",
    )
    _insert_run(
        db_path,
        run_id="r2",
        local_id="r2",
        model="gpt-5.3-codex",
        status="failed",
        workspace_id="w1",
        duration_secs=3.0,
        total_cost_usd=0.0,
        harness_session_id="sess-a",
    )
    _insert_run(
        db_path,
        run_id="r3",
        local_id="r3",
        model="claude-sonnet-4-6",
        status="cancelled",
        workspace_id="w2",
        duration_secs=1.0,
        total_cost_usd=0.1,
        harness_session_id="sess-b",
    )
    _insert_run(
        db_path,
        run_id="r4",
        local_id="r4",
        model="claude-sonnet-4-6",
        status="running",
        workspace_id=None,
        duration_secs=None,
        total_cost_usd=None,
        harness_session_id="sess-b",
    )
    _insert_run(
        db_path,
        run_id="r5",
        local_id="r5",
        model="opencode-gpt-5.3-codex",
        status="queued",
        workspace_id=None,
        duration_secs=None,
        total_cost_usd=None,
        harness_session_id="sess-c",
    )

    result = run_stats_sync(RunStatsInput(repo_root=tmp_path.as_posix()))
    assert result.total_runs == 5
    assert result.succeeded == 1
    assert result.failed == 1
    assert result.cancelled == 1
    assert result.running == 1
    assert result.total_duration_secs == 6.5
    assert result.total_cost_usd == 0.35
    assert result.models == {
        "claude-sonnet-4-6": 2,
        "gpt-5.3-codex": 2,
        "opencode-gpt-5.3-codex": 1,
    }


def test_run_stats_sync_filters_by_workspace_and_session(tmp_path: Path) -> None:
    db_path = resolve_state_paths(tmp_path).db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        apply_migrations(conn)
    finally:
        conn.close()

    _insert_run(
        db_path,
        run_id="r1",
        local_id="r1",
        model="gpt-5.3-codex",
        status="succeeded",
        workspace_id="w1",
        duration_secs=1.0,
        total_cost_usd=0.1,
        harness_session_id="sess-1",
    )
    _insert_run(
        db_path,
        run_id="r2",
        local_id="r2",
        model="gpt-5.3-codex",
        status="failed",
        workspace_id="w1",
        duration_secs=2.0,
        total_cost_usd=0.2,
        harness_session_id="sess-2",
    )
    _insert_run(
        db_path,
        run_id="r3",
        local_id="r3",
        model="claude-sonnet-4-6",
        status="succeeded",
        workspace_id="w2",
        duration_secs=3.0,
        total_cost_usd=0.3,
        harness_session_id="sess-1",
    )

    result = run_stats_sync(
        RunStatsInput(
            repo_root=tmp_path.as_posix(),
            workspace="w1",
            session="sess-1",
        )
    )
    assert result.total_runs == 1
    assert result.succeeded == 1
    assert result.failed == 0
    assert result.cancelled == 0
    assert result.running == 0
    assert result.total_duration_secs == 1.0
    assert result.total_cost_usd == 0.1
    assert result.models == {"gpt-5.3-codex": 1}


def test_run_stats_sync_ignores_session_filter_when_no_session_column(tmp_path: Path) -> None:
    db_path = resolve_state_paths(tmp_path).db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            conn.execute(
                """
                CREATE TABLE runs (
                    id TEXT PRIMARY KEY,
                    workspace_id TEXT,
                    model TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration_secs REAL,
                    total_cost_usd REAL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO runs(id, workspace_id, model, status, duration_secs, total_cost_usd)
                VALUES
                    ('r1', 'w1', 'gpt-5.3-codex', 'succeeded', 1.0, 0.1),
                    ('r2', 'w1', 'gpt-5.3-codex', 'failed', 2.0, 0.2)
                """
            )
    finally:
        conn.close()

    result = run_stats_sync(
        RunStatsInput(
            repo_root=tmp_path.as_posix(),
            workspace="w1",
            session="sess-missing",
        )
    )
    assert result.total_runs == 2
    assert result.succeeded == 1
    assert result.failed == 1
