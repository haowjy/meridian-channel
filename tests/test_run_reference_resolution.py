"""Run reference resolution tests for @latest/@last-failed/@last-completed."""

from __future__ import annotations

from pathlib import Path

import pytest

import meridian.lib.ops.run as run_ops
from meridian.lib.ops._run_query import resolve_run_reference
from meridian.lib.ops.run import (
    RunActionOutput,
    RunContinueInput,
    RunShowInput,
    RunWaitInput,
)
from meridian.lib.space.space_file import create_space
from meridian.lib.state import run_store
from meridian.lib.state.paths import resolve_space_dir


def _create_run(space_dir: Path, *, prompt: str, status: str) -> str:
    run_id = run_store.start_run(
        space_dir,
        session_id="c1",
        model="gpt-5.3-codex",
        agent="coder",
        harness="codex",
        prompt=prompt,
    )
    if status != "running":
        exit_code = 0 if status == "succeeded" else 1
        run_store.finalize_run(space_dir, run_id, status, exit_code)
    return str(run_id)


def test_resolve_run_reference_selectors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    space = create_space(tmp_path, name="refs")
    space_dir = resolve_space_dir(tmp_path, space.id)
    monkeypatch.setenv("MERIDIAN_SPACE_ID", space.id)

    run1 = _create_run(space_dir, prompt="first", status="succeeded")
    run2 = _create_run(space_dir, prompt="second", status="failed")
    run3 = _create_run(space_dir, prompt="third", status="succeeded")

    assert resolve_run_reference(tmp_path, "@latest") == run3
    assert resolve_run_reference(tmp_path, "@last-failed") == run2
    assert resolve_run_reference(tmp_path, "@last-completed") == run3
    assert resolve_run_reference(tmp_path, run1) == run1


def test_resolve_run_reference_raises_for_empty_unknown_or_missing_selector(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    space = create_space(tmp_path, name="refs")
    space_dir = resolve_space_dir(tmp_path, space.id)
    monkeypatch.setenv("MERIDIAN_SPACE_ID", space.id)

    _ = _create_run(space_dir, prompt="only", status="succeeded")

    with pytest.raises(ValueError, match="run_id is required"):
        resolve_run_reference(tmp_path, "   ")

    with pytest.raises(ValueError, match="Unknown run reference '@nope'"):
        resolve_run_reference(tmp_path, "@nope")

    with pytest.raises(ValueError, match="No runs found for reference '@last-failed'"):
        resolve_run_reference(tmp_path, "@last-failed")


def test_run_show_and_wait_accept_run_references(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    space = create_space(tmp_path, name="refs")
    space_dir = resolve_space_dir(tmp_path, space.id)
    monkeypatch.setenv("MERIDIAN_SPACE_ID", space.id)

    run1 = _create_run(space_dir, prompt="ok", status="succeeded")
    run2 = _create_run(space_dir, prompt="broken", status="failed")

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
    assert run1 != run2


def test_run_continue_and_retry_accept_latest_reference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    space = create_space(tmp_path, name="refs")
    space_dir = resolve_space_dir(tmp_path, space.id)
    monkeypatch.setenv("MERIDIAN_SPACE_ID", space.id)

    run_id = _create_run(space_dir, prompt="stored prompt", status="succeeded")

    captured_payloads: list[object] = []

    def fake_run_create_sync(payload: object) -> RunActionOutput:
        captured_payloads.append(payload)
        return RunActionOutput(
            command="run.spawn",
            status="succeeded",
            run_id=f"r-next-{len(captured_payloads)}",
        )

    monkeypatch.setattr(run_ops, "run_create_sync", fake_run_create_sync)

    continued = run_ops.run_continue_sync(
        RunContinueInput(run_id="@latest", prompt="", repo_root=tmp_path.as_posix())
    )

    assert continued.command == "run.continue"
    assert len(captured_payloads) == 1
    assert getattr(captured_payloads[0], "prompt") == "stored prompt"
    assert resolve_run_reference(tmp_path, "@latest") == run_id
