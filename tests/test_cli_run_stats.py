"""CLI plumbing for run.stats."""

from __future__ import annotations

import json
from pathlib import Path

from meridian.cli import run as run_cli
from meridian.lib.ops.run import RunStatsInput, RunStatsOutput
from meridian.lib.space.space_file import create_space


def test_run_stats_passes_session_and_space_filters(monkeypatch) -> None:
    captured: dict[str, RunStatsInput] = {}
    emitted: list[RunStatsOutput] = []

    def fake_run_stats_sync(payload: RunStatsInput) -> RunStatsOutput:
        captured["payload"] = payload
        return RunStatsOutput(
            total_runs=1,
            succeeded=1,
            failed=0,
            cancelled=0,
            running=0,
            total_duration_secs=2.0,
            total_cost_usd=0.1,
            models={"gpt-5.3-codex": 1},
        )

    monkeypatch.setattr(run_cli, "run_stats_sync", fake_run_stats_sync)

    run_cli._run_stats(
        emitted.append,
        session="sess-1",
        space="s1",
    )

    assert captured["payload"] == RunStatsInput(session="sess-1", space="s1")
    assert emitted[0].total_runs == 1
    assert emitted[0].models == {"gpt-5.3-codex": 1}


def test_cli_run_stats_json_output(
    run_meridian,
    cli_env: dict[str, str],
    tmp_path: Path,
) -> None:
    cli_env["MERIDIAN_REPO_ROOT"] = tmp_path.as_posix()
    space = create_space(tmp_path, name="cli-stats")
    cli_env["MERIDIAN_SPACE_ID"] = space.id

    result = run_meridian(["--json", "run", "stats"])
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["total_runs"] >= 0
    assert "models" in payload
