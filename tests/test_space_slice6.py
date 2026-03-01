"""Slice 6 space/diag integration checks."""

from __future__ import annotations

import importlib
import json
import shlex
import sys
from pathlib import Path

import pytest

import meridian.lib.ops.run as run_ops
from meridian.lib.ops.diag import DiagRepairInput, diag_repair_sync
from meridian.lib.ops.run import (
    RunActionOutput,
    RunContinueInput,
    RunCreateInput,
    run_continue_sync,
    run_create_sync,
)
from meridian.lib.ops.space import (
    SpaceResumeInput,
    SpaceStartInput,
    space_resume_sync,
    space_start_sync,
)
from meridian.lib.space import crud as space_crud
from meridian.lib.space.space_file import create_space, get_space
from meridian.lib.state import run_store
from meridian.lib.state.paths import resolve_space_dir


def _harness_command(package_root: Path, capture_path: Path) -> str:
    parts = [
        sys.executable,
        str(package_root / "tests" / "mock_harness.py"),
        "--duration",
        "0",
        "--capture-json",
        str(capture_path),
    ]
    return " ".join(shlex.quote(part) for part in parts)


def _capture_payload(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_space_start_creates_lock_sets_env_and_forwards_passthrough(
    package_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture = tmp_path / "start-capture.json"
    monkeypatch.setenv("MERIDIAN_HARNESS_COMMAND", _harness_command(package_root, capture))

    result = space_start_sync(
        SpaceStartInput(
            name="slice6",
            autocompact=72,
            harness_args=("--demo-flag", "enabled"),
            repo_root=tmp_path.as_posix(),
        )
    )

    assert result.space_id == "s1"
    assert result.state == "active"
    assert result.exit_code == 0
    assert result.lock_path is not None
    assert not Path(result.lock_path).exists()

    payload = _capture_payload(capture)
    env = payload["env"]
    assert isinstance(env, dict)
    assert env["MERIDIAN_SPACE_ID"] == result.space_id
    assert env["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"] == "72"

    argv = payload["argv"]
    assert isinstance(argv, list)
    assert "--autocompact" in argv
    assert "72" in argv
    assert "--demo-flag" in argv
    assert "enabled" in argv

    assert result.summary_path is not None
    assert Path(result.summary_path).exists()


def test_space_resume_fresh_omits_continuation_guidance(
    package_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    space = create_space(tmp_path, name="fresh")

    capture = tmp_path / "fresh-capture.json"
    monkeypatch.setenv("MERIDIAN_HARNESS_COMMAND", _harness_command(package_root, capture))

    result = space_resume_sync(
        SpaceResumeInput(
            space=space.id,
            fresh=True,
            repo_root=tmp_path.as_posix(),
        )
    )
    assert result.state == "active"

    payload = _capture_payload(capture)
    env = payload["env"]
    assert isinstance(env, dict)
    prompt = env["MERIDIAN_SPACE_PROMPT"]
    assert isinstance(prompt, str)
    assert "Continuation Guidance" not in prompt
    assert "fresh primary conversation" in prompt


def test_space_resume_rejects_closed_space(tmp_path: Path) -> None:
    created = create_space(tmp_path, name="resume-closed")
    space_crud.transition_space(tmp_path, created.id, "closed")

    with pytest.raises(ValueError, match="is closed and cannot resume"):
        space_resume_sync(
            SpaceResumeInput(
                space=created.id,
                repo_root=tmp_path.as_posix(),
            )
        )


def test_space_state_machine_blocks_invalid_terminal_resume(tmp_path: Path) -> None:
    created = create_space(tmp_path, name="terminal")

    space_crud.transition_space(tmp_path, created.id, "closed")
    with pytest.raises(ValueError, match="Invalid space transition"):
        space_crud.transition_space(tmp_path, created.id, "active")


@pytest.mark.parametrize(
    "status",
    [
        pytest.param("running", id="running"),
        pytest.param("failed", id="failed"),
        pytest.param("succeeded", id="succeeded"),
    ],
)
def test_run_continue_works_for_running_failed_and_succeeded(
    status: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    space = create_space(tmp_path, name="continue")
    space_dir = resolve_space_dir(tmp_path, space.id)
    monkeypatch.setenv("MERIDIAN_SPACE_ID", space.id)

    run_id = run_store.start_run(
        space_dir,
        session_id="c1",
        model="gpt-5.3-codex",
        agent="coder",
        harness="codex",
        prompt="original prompt",
        harness_session_id="sess-source",
    )
    if status != "running":
        run_store.finalize_run(
            space_dir,
            run_id,
            status,
            0 if status == "succeeded" else 1,
        )

    captured: dict[str, object] = {}

    def fake_run_create_sync(payload: RunCreateInput) -> RunActionOutput:
        captured["payload"] = payload
        return RunActionOutput(
            command="run.create",
            status="succeeded",
            run_id="r-next",
            message="ok",
        )

    monkeypatch.setattr(run_ops, "run_create_sync", fake_run_create_sync)

    result = run_continue_sync(
        RunContinueInput(
            run_id=str(run_id),
            prompt="",
            fork=True,
            repo_root=tmp_path.as_posix(),
        )
    )

    assert result.command == "run.continue"
    forwarded = captured["payload"]
    assert isinstance(forwarded, RunCreateInput)
    assert forwarded.prompt == "original prompt"
    assert forwarded.model == "gpt-5.3-codex"
    assert forwarded.continue_harness == "codex"
    assert forwarded.continue_session_id == "sess-source"
    assert forwarded.continue_fork is True


def test_run_create_dry_run_fallbacks_for_harness_mismatch_and_missing_fork_support(
    tmp_path: Path,
) -> None:
    mismatch = run_create_sync(
        RunCreateInput(
            prompt="continue mismatch",
            model="gpt-5.3-codex",
            dry_run=True,
            repo_root=tmp_path.as_posix(),
            continue_session_id="sess-a",
            continue_harness="claude",
            continue_fork=True,
        )
    )
    assert mismatch.status == "dry-run"
    assert "resume" not in mismatch.cli_command
    assert mismatch.warning is not None
    assert "target harness differs" in mismatch.warning

    no_fork_support = run_create_sync(
        RunCreateInput(
            prompt="continue codex",
            model="gpt-5.3-codex",
            dry_run=True,
            repo_root=tmp_path.as_posix(),
            continue_session_id="sess-b",
            continue_harness="codex",
            continue_fork=True,
        )
    )
    assert no_fork_support.status == "dry-run"
    assert no_fork_support.cli_command[:4] == ("codex", "exec", "resume", "sess-b")
    assert no_fork_support.warning is not None
    assert "does not support session fork" in no_fork_support.warning


def test_diag_repair_rebuilds_stale_state_and_orphan_runs(tmp_path: Path) -> None:
    created = create_space(tmp_path, name="stuck-active")
    space_dir = resolve_space_dir(tmp_path, created.id)

    _ = run_store.start_run(
        space_dir,
        session_id="c1",
        model="gpt-5.3-codex",
        agent="coder",
        harness="codex",
        prompt="repair",
    )

    sessions_dir = space_dir / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    stale_lock = sessions_dir / "c9.lock"
    stale_lock.write_text("", encoding="utf-8")

    repaired = diag_repair_sync(DiagRepairInput(repo_root=tmp_path.as_posix()))
    assert repaired.ok is True
    assert "orphan_runs" in repaired.repaired
    assert "stale_session_locks" in repaired.repaired
    assert "stale_space_status" in repaired.repaired
    assert not stale_lock.exists()

    refreshed_space = get_space(tmp_path, created.id)
    assert refreshed_space is not None
    assert refreshed_space.status == "closed"


def test_start_alias_forwards_space_start_options(monkeypatch: pytest.MonkeyPatch) -> None:
    main_module = importlib.import_module("meridian.cli.main")
    captured: dict[str, list[str]] = {}

    def fake_space_app(tokens: list[str]) -> None:
        captured["tokens"] = list(tokens)

    monkeypatch.setattr(main_module, "space_app", fake_space_app)

    with pytest.raises(SystemExit) as exc:
        main_module.app(["start", "--autocompact", "72", "--harness-arg", "enabled"])

    assert exc.value.code == 0
    assert captured["tokens"] == [
        "start",
        "--autocompact",
        "72",
        "--harness-arg",
        "enabled",
    ]
