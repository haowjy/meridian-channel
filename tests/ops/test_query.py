"""Running-spawn query parser regressions and detail shaping."""


import json
from pathlib import Path

from meridian.lib.ops.spawn.models import SpawnDetailOutput, SpawnWaitMultiOutput
from meridian.lib.ops.spawn.query import detail_from_row, extract_last_assistant_message
from meridian.lib.state.spawn_store import SpawnRecord


def test_extract_last_assistant_message_ignores_codex_substrings() -> None:
    stderr_text = "\n".join(
        [
            "OpenAI Codex v0.107.0",
            "model=gpt-5.3-codex",
            "harness=codex",
            "provider=openai",
        ]
    )
    assert extract_last_assistant_message(stderr_text) is None


def test_extract_last_assistant_message_reads_lines_after_codex_marker() -> None:
    stderr_text = "\n".join(
        [
            "OpenAI Codex v0.107.0",
            "model: gpt-5.3-codex",
            "codex",
            "First response line.",
            "Second response line.",
            "exec",
            "/bin/bash -lc 'echo ok'",
            "codex",
            "Final assistant reply.",
        ]
    )
    assert extract_last_assistant_message(stderr_text) == "Final assistant reply."


def test_extract_last_assistant_message_keeps_json_assistant_events() -> None:
    stderr_text = "\n".join(
        [
            json.dumps({"type": "assistant", "text": "json assistant message"}),
            "exec",
        ]
    )
    assert extract_last_assistant_message(stderr_text) == "json assistant message"


def test_detail_from_row_carries_work_and_desc_fields(tmp_path: Path) -> None:
    row = SpawnRecord(
        id="p5",
        chat_id="c1",
        model="claude-opus-4-6",
        agent="agent",
        harness="claude",
        kind="child",
        desc="Implement step 2",
        work_id="auth-refactor",
        harness_session_id="session-1",
        launch_mode="foreground",
        wrapper_pid=None,
        worker_pid=None,
        status="running",
        prompt="ignored",
        started_at="2026-03-09T00:00:00Z",
        finished_at=None,
        exit_code=None,
        duration_secs=238.8,
        total_cost_usd=None,
        input_tokens=None,
        output_tokens=None,
        error=None,
    )

    result = detail_from_row(repo_root=tmp_path, row=row, include_report_body=False)

    assert result.work_id == "auth-refactor"
    assert result.desc == "Implement step 2"


def test_detail_from_row_keeps_report_path_without_loading_body(tmp_path: Path) -> None:
    spawn_dir = tmp_path / ".meridian" / "spawns" / "p5"
    spawn_dir.mkdir(parents=True)
    (spawn_dir / "report.md").write_text("# Summary\n\nDone.\n", encoding="utf-8")
    row = SpawnRecord(
        id="p5",
        chat_id="c1",
        model="claude-opus-4-6",
        agent="agent",
        harness="claude",
        kind="child",
        desc=None,
        work_id=None,
        harness_session_id="session-1",
        launch_mode="foreground",
        wrapper_pid=None,
        worker_pid=None,
        status="succeeded",
        prompt="ignored",
        started_at="2026-03-09T00:00:00Z",
        finished_at="2026-03-09T00:00:10Z",
        exit_code=0,
        duration_secs=10.0,
        total_cost_usd=None,
        input_tokens=None,
        output_tokens=None,
        error=None,
    )

    result = detail_from_row(repo_root=tmp_path, row=row, include_report_body=False)

    assert result.report_path == (spawn_dir / "report.md").as_posix()
    assert result.report_body is None


def test_spawn_detail_format_text_shows_work_and_desc_when_present() -> None:
    payload = SpawnDetailOutput(
        spawn_id="p5",
        status="running",
        model="claude-opus-4-6",
        harness="claude",
        work_id="auth-refactor",
        desc="Implement step 2",
        started_at="2026-03-09T00:00:00Z",
        finished_at=None,
        duration_secs=238.8,
        exit_code=None,
        failure_reason=None,
        input_tokens=None,
        output_tokens=None,
        cost_usd=None,
        report_path="/tmp/.meridian/spawns/p5/report.md",
        report_summary=None,
        report_body=None,
        last_message=None,
        log_path=None,
    )

    assert payload.format_text() == "\n".join(
        [
            "Spawn: p5",
            "Status: running",
            "Model: claude-opus-4-6 (claude)",
            "Duration: 238.8s",
            "Work: auth-refactor",
            "Desc: Implement step 2",
            "Report: /tmp/.meridian/spawns/p5/report.md",
        ]
    )


def test_spawn_detail_format_text_omits_blank_work_and_desc() -> None:
    payload = SpawnDetailOutput(
        spawn_id="p5",
        status="running",
        model="claude-opus-4-6",
        harness="claude",
        work_id="   ",
        desc="",
        started_at="2026-03-09T00:00:00Z",
        finished_at=None,
        duration_secs=238.8,
        exit_code=None,
        failure_reason=None,
        input_tokens=None,
        output_tokens=None,
        cost_usd=None,
        report_path=None,
        report_summary=None,
        report_body=None,
        last_message=None,
        log_path=None,
    )

    assert payload.format_text() == "\n".join(
        [
            "Spawn: p5",
            "Status: running",
            "Model: claude-opus-4-6 (claude)",
            "Duration: 238.8s",
        ]
    )


def test_spawn_detail_format_text_appends_report_body_when_present() -> None:
    payload = SpawnDetailOutput(
        spawn_id="p148",
        status="succeeded",
        model="claude-opus-4-6",
        harness="claude",
        work_id=None,
        desc=None,
        started_at="2026-03-09T00:00:00Z",
        finished_at="2026-03-09T00:14:50Z",
        duration_secs=890.3,
        exit_code=0,
        failure_reason=None,
        input_tokens=None,
        output_tokens=None,
        cost_usd=3.9832,
        report_path="/tmp/.meridian/spawns/p148/report.md",
        report_summary="# Summary",
        report_body="# Summary\n\nActual work is done.",
        last_message=None,
        log_path=None,
    )

    assert payload.format_text() == "\n".join(
        [
            "Spawn: p148",
            "Status: succeeded (exit 0)",
            "Model: claude-opus-4-6 (claude)",
            "Duration: 890.3s",
            "Cost: $3.9832",
            "Report: /tmp/.meridian/spawns/p148/report.md",
            "",
            "# Summary",
            "",
            "Actual work is done.",
        ]
    )


def test_spawn_wait_multi_format_text_uses_detail_view_for_single_spawn() -> None:
    spawn = SpawnDetailOutput(
        spawn_id="p148",
        status="succeeded",
        model="claude-opus-4-6",
        harness="claude",
        work_id=None,
        desc=None,
        started_at="2026-03-09T00:00:00Z",
        finished_at="2026-03-09T00:14:50Z",
        duration_secs=890.3,
        exit_code=0,
        failure_reason=None,
        input_tokens=None,
        output_tokens=None,
        cost_usd=3.9832,
        report_path="/tmp/.meridian/spawns/p148/report.md",
        report_summary="# Summary",
        report_body="# Summary\n\nActual work is done.",
        last_message=None,
        log_path=None,
    )
    payload = SpawnWaitMultiOutput(
        spawns=(spawn,),
        total_runs=1,
        succeeded_runs=1,
        failed_runs=0,
        cancelled_runs=0,
        any_failed=False,
        spawn_id="p148",
        status="succeeded",
        exit_code=0,
    )

    assert payload.format_text() == spawn.format_text()


def test_spawn_wait_multi_format_text_includes_report_column_for_multiple_spawns() -> None:
    first = SpawnDetailOutput(
        spawn_id="p1",
        status="succeeded",
        model="claude-opus-4-6",
        harness="claude",
        work_id=None,
        desc=None,
        started_at="2026-03-09T00:00:00Z",
        finished_at="2026-03-09T00:00:10Z",
        duration_secs=10.0,
        exit_code=0,
        failure_reason=None,
        input_tokens=None,
        output_tokens=None,
        cost_usd=None,
        report_path="/tmp/.meridian/spawns/p1/report.md",
        report_summary=None,
        report_body=None,
        last_message=None,
        log_path=None,
    )
    second = SpawnDetailOutput(
        spawn_id="p2",
        status="failed",
        model="gpt-5.3-codex",
        harness="codex",
        work_id=None,
        desc=None,
        started_at="2026-03-09T00:00:00Z",
        finished_at="2026-03-09T00:00:12Z",
        duration_secs=12.0,
        exit_code=1,
        failure_reason="boom",
        input_tokens=None,
        output_tokens=None,
        cost_usd=None,
        report_path=None,
        report_summary=None,
        report_body=None,
        last_message=None,
        log_path=None,
    )
    payload = SpawnWaitMultiOutput(
        spawns=(first, second),
        total_runs=2,
        succeeded_runs=1,
        failed_runs=1,
        cancelled_runs=0,
        any_failed=True,
        spawn_id=None,
        status=None,
        exit_code=None,
    )

    assert payload.format_text() == "\n".join(
        [
            "spawn_id  status     duration  exit  report",
            "p1        succeeded  10.0s     0     /tmp/.meridian/spawns/p1/report.md",
            "p2        failed     12.0s     1     -",
        ]
    )


def test_spawn_wait_multi_format_text_appends_report_sections_for_multiple_spawns() -> None:
    first = SpawnDetailOutput(
        spawn_id="p1",
        status="succeeded",
        model="claude-opus-4-6",
        harness="claude",
        work_id=None,
        desc=None,
        started_at="2026-03-09T00:00:00Z",
        finished_at="2026-03-09T00:00:10Z",
        duration_secs=10.0,
        exit_code=0,
        failure_reason=None,
        input_tokens=None,
        output_tokens=None,
        cost_usd=None,
        report_path="/tmp/.meridian/spawns/p1/report.md",
        report_summary="# First",
        report_body="# First",
        last_message=None,
        log_path=None,
    )
    second = SpawnDetailOutput(
        spawn_id="p2",
        status="failed",
        model="gpt-5.3-codex",
        harness="codex",
        work_id=None,
        desc=None,
        started_at="2026-03-09T00:00:00Z",
        finished_at="2026-03-09T00:00:12Z",
        duration_secs=12.0,
        exit_code=1,
        failure_reason="boom",
        input_tokens=None,
        output_tokens=None,
        cost_usd=None,
        report_path=None,
        report_summary=None,
        report_body=None,
        last_message=None,
        log_path=None,
    )
    payload = SpawnWaitMultiOutput(
        spawns=(first, second),
        total_runs=2,
        succeeded_runs=1,
        failed_runs=1,
        cancelled_runs=0,
        any_failed=True,
        spawn_id=None,
        status=None,
        exit_code=None,
    )

    assert payload.format_text() == "\n".join(
        [
            "spawn_id  status     duration  exit  report",
            "p1        succeeded  10.0s     0     /tmp/.meridian/spawns/p1/report.md",
            "p2        failed     12.0s     1     -",
            "",
            "Report for p1",
            "# First",
        ]
    )
