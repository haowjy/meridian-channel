"""run.stats aggregate and filter behavior."""

from __future__ import annotations

from pathlib import Path

from meridian.lib.ops.run import RunStatsInput, run_stats_sync
from meridian.lib.space.space_file import create_space
from meridian.lib.state import run_store
from meridian.lib.state.paths import resolve_space_dir


def _start_and_finalize(
    space_dir: Path,
    *,
    model: str,
    status: str,
    session_id: str,
    duration_secs: float | None = None,
    total_cost_usd: float | None = None,
) -> str:
    run_id = run_store.start_run(
        space_dir,
        session_id=session_id,
        model=model,
        agent="coder",
        harness="codex",
        prompt="stats",
    )
    if status != "running":
        run_store.finalize_run(
            space_dir,
            run_id,
            status,
            0 if status == "succeeded" else 1,
            duration_secs=duration_secs,
            total_cost_usd=total_cost_usd,
        )
    return str(run_id)


def test_run_stats_sync_aggregates_all_runs(tmp_path: Path, monkeypatch) -> None:
    space = create_space(tmp_path, name="stats")
    space_dir = resolve_space_dir(tmp_path, space.id)
    monkeypatch.setenv("MERIDIAN_SPACE_ID", space.id)

    _start_and_finalize(
        space_dir,
        model="gpt-5.3-codex",
        status="succeeded",
        session_id="c1",
        duration_secs=2.5,
        total_cost_usd=0.25,
    )
    _start_and_finalize(
        space_dir,
        model="gpt-5.3-codex",
        status="failed",
        session_id="c1",
        duration_secs=3.0,
        total_cost_usd=0.0,
    )
    _start_and_finalize(
        space_dir,
        model="claude-sonnet-4-6",
        status="cancelled",
        session_id="c2",
        duration_secs=1.0,
        total_cost_usd=0.1,
    )
    _start_and_finalize(
        space_dir,
        model="claude-sonnet-4-6",
        status="running",
        session_id="c2",
    )

    result = run_stats_sync(RunStatsInput(repo_root=tmp_path.as_posix()))
    assert result.total_runs == 4
    assert result.succeeded == 1
    assert result.failed == 1
    assert result.cancelled == 1
    assert result.running == 1
    assert result.total_duration_secs == 6.5
    assert result.total_cost_usd == 0.35
    assert result.models == {
        "claude-sonnet-4-6": 2,
        "gpt-5.3-codex": 2,
    }


def test_run_stats_sync_filters_by_space_and_session(tmp_path: Path, monkeypatch) -> None:
    space = create_space(tmp_path, name="stats")
    space_dir = resolve_space_dir(tmp_path, space.id)
    monkeypatch.setenv("MERIDIAN_SPACE_ID", space.id)

    _start_and_finalize(
        space_dir,
        model="gpt-5.3-codex",
        status="succeeded",
        session_id="c1",
        duration_secs=1.0,
        total_cost_usd=0.1,
    )
    _start_and_finalize(
        space_dir,
        model="gpt-5.3-codex",
        status="failed",
        session_id="c2",
        duration_secs=2.0,
        total_cost_usd=0.2,
    )

    result = run_stats_sync(
        RunStatsInput(
            repo_root=tmp_path.as_posix(),
            space=space.id,
            session="c1",
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


def test_run_stats_sync_returns_empty_for_non_current_space(tmp_path: Path, monkeypatch) -> None:
    first = create_space(tmp_path, name="first")
    first_dir = resolve_space_dir(tmp_path, first.id)
    second = create_space(tmp_path, name="second")
    _ = resolve_space_dir(tmp_path, second.id)
    monkeypatch.setenv("MERIDIAN_SPACE_ID", first.id)

    _start_and_finalize(
        first_dir,
        model="gpt-5.3-codex",
        status="succeeded",
        session_id="c1",
        duration_secs=1.0,
        total_cost_usd=0.1,
    )

    result = run_stats_sync(
        RunStatsInput(
            repo_root=tmp_path.as_posix(),
            space=second.id,
        )
    )
    assert result.total_runs == 0
    assert result.succeeded == 0
    assert result.failed == 0
