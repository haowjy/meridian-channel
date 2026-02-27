"""Run reference resolution tests for @latest/@last-failed/@last-completed."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import cast

import pytest

import meridian.lib.ops.run as run_ops
from meridian.lib.adapters.sqlite import StateDB
from meridian.lib.domain import RunCreateParams, RunStatus
from meridian.lib.ops._run_query import resolve_run_reference
from meridian.lib.ops.run import (
    RunActionOutput,
    RunContinueInput,
    RunRetryInput,
    RunShowInput,
    RunWaitInput,
)
from meridian.lib.state.db import resolve_state_paths
from meridian.lib.types import ModelId


def _create_run(state: StateDB, *, prompt: str, status: str) -> str:
    run = state.create_run(
        RunCreateParams(
            prompt=prompt,
            model=ModelId("gpt-5.3-codex"),
        )
    )
    state.update_run_status(run.run_id, cast(RunStatus, status))
    return str(run.run_id)


def _set_started_at(repo_root: Path, run_id: str, started_at: str) -> None:
    db_path = resolve_state_paths(repo_root).db_path
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            conn.execute(
                "UPDATE runs SET started_at = ? WHERE id = ?",
                (started_at, run_id),
            )
    finally:
        conn.close()


def test_resolve_run_reference_selectors(tmp_path: Path) -> None:
    state = StateDB(tmp_path)
    run1 = _create_run(state, prompt="first", status="succeeded")
    run2 = _create_run(state, prompt="second", status="failed")
    run3 = _create_run(state, prompt="third", status="succeeded")

    _set_started_at(tmp_path, run1, "2026-02-27T00:00:01Z")
    _set_started_at(tmp_path, run2, "2026-02-27T00:00:02Z")
    _set_started_at(tmp_path, run3, "2026-02-27T00:00:03Z")

    assert resolve_run_reference(tmp_path, "@latest") == run3
    assert resolve_run_reference(tmp_path, "@last-failed") == run2
    assert resolve_run_reference(tmp_path, "@last-completed") == run3
    assert resolve_run_reference(tmp_path, run1) == run1


def test_resolve_run_reference_raises_for_empty_unknown_or_missing_selector(tmp_path: Path) -> None:
    state = StateDB(tmp_path)
    run1 = _create_run(state, prompt="only", status="succeeded")
    _set_started_at(tmp_path, run1, "2026-02-27T00:00:01Z")

    with pytest.raises(ValueError, match="run_id is required"):
        resolve_run_reference(tmp_path, "   ")

    with pytest.raises(ValueError, match="Unknown run reference '@nope'"):
        resolve_run_reference(tmp_path, "@nope")

    with pytest.raises(ValueError, match="No runs found for reference '@last-failed'"):
        resolve_run_reference(tmp_path, "@last-failed")


def test_run_show_and_wait_accept_run_references(tmp_path: Path) -> None:
    state = StateDB(tmp_path)
    run1 = _create_run(state, prompt="ok", status="succeeded")
    run2 = _create_run(state, prompt="broken", status="failed")

    _set_started_at(tmp_path, run1, "2026-02-27T00:00:01Z")
    _set_started_at(tmp_path, run2, "2026-02-27T00:00:02Z")

    shown_latest = run_ops.run_show_sync(
        RunShowInput(run_id="@latest", repo_root=tmp_path.as_posix())
    )
    shown_failed = run_ops.run_show_sync(
        RunShowInput(run_id="@last-failed", repo_root=tmp_path.as_posix())
    )
    waited = run_ops.run_wait_sync(
        RunWaitInput(run_ids=("@latest",), repo_root=tmp_path.as_posix(), poll_interval_secs=0.0)
    )

    assert shown_latest.run_id == run2
    assert shown_failed.run_id == run2
    assert waited.run_id == run2
    assert waited.status == "failed"


def test_run_continue_and_retry_accept_latest_reference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = StateDB(tmp_path)
    run_id = _create_run(state, prompt="stored prompt", status="succeeded")
    _set_started_at(tmp_path, run_id, "2026-02-27T00:00:01Z")

    captured_payloads: list[object] = []

    def fake_run_create_sync(payload: object) -> RunActionOutput:
        captured_payloads.append(payload)
        return RunActionOutput(
            command="run.create",
            status="succeeded",
            run_id=f"r-next-{len(captured_payloads)}",
        )

    monkeypatch.setattr(run_ops, "run_create_sync", fake_run_create_sync)

    continued = run_ops.run_continue_sync(
        RunContinueInput(run_id="@latest", prompt="", repo_root=tmp_path.as_posix())
    )
    retried = run_ops.run_retry_sync(
        RunRetryInput(run_id="@latest", prompt=None, repo_root=tmp_path.as_posix())
    )

    assert continued.command == "run.continue"
    assert retried.command == "run.retry"
    assert len(captured_payloads) == 2
    assert getattr(captured_payloads[0], "prompt") == "stored prompt"
    assert getattr(captured_payloads[1], "prompt") == "stored prompt"
