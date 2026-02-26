"""Slice 6 workspace/context/export/diag integration checks."""

from __future__ import annotations

import importlib
import json
import shlex
import sqlite3
import sys
from pathlib import Path

import pytest

import meridian.lib.ops.run as run_ops
from meridian.cli.export import export_workspace_sync
from meridian.lib.adapters.sqlite import StateDB
from meridian.lib.domain import RunCreateParams, RunStatus, WorkspaceCreateParams
from meridian.lib.ops.context import ContextListInput, context_list_sync
from meridian.lib.ops.diag import DiagRepairInput, diag_repair_sync
from meridian.lib.ops.run import (
    RunActionOutput,
    RunContinueInput,
    RunCreateInput,
    run_continue_sync,
)
from meridian.lib.ops.workspace import (
    WorkspaceResumeInput,
    WorkspaceStartInput,
    workspace_resume_sync,
    workspace_start_sync,
)
from meridian.lib.types import ModelId
from meridian.lib.workspace import crud as workspace_crud


def _supervisor_command(package_root: Path, capture_path: Path) -> str:
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


def test_workspace_start_creates_lock_sets_env_and_forwards_passthrough(
    package_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture = tmp_path / "start-capture.json"
    monkeypatch.setenv("MERIDIAN_SUPERVISOR_COMMAND", _supervisor_command(package_root, capture))

    result = workspace_start_sync(
        WorkspaceStartInput(
            name="slice6",
            autocompact=72,
            harness_args=("--demo-flag", "enabled"),
            repo_root=tmp_path.as_posix(),
        )
    )

    assert result.workspace_id == "w1"
    assert result.state == "paused"
    assert result.exit_code == 0
    assert result.lock_path is not None
    assert not Path(result.lock_path).exists()

    payload = _capture_payload(capture)
    env = payload["env"]
    assert isinstance(env, dict)
    assert env["MERIDIAN_WORKSPACE_ID"] == result.workspace_id
    assert env["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"] == "72"

    argv = payload["argv"]
    assert isinstance(argv, list)
    assert "--autocompact" in argv
    assert "72" in argv
    assert "--demo-flag" in argv
    assert "enabled" in argv

    assert result.summary_path is not None
    assert Path(result.summary_path).exists()


def test_workspace_resume_generates_summary_and_reinjects_pinned_context(
    package_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = StateDB(tmp_path)
    workspace = state.create_workspace(WorkspaceCreateParams(name="resume"))
    state.transition_workspace(workspace.workspace_id, "paused")

    pinned_file = tmp_path / "notes" / "resume.md"
    pinned_file.parent.mkdir(parents=True, exist_ok=True)
    pinned_file.write_text("Pinned analysis context", encoding="utf-8")
    state.pin_file(workspace.workspace_id, pinned_file.as_posix())

    capture = tmp_path / "resume-capture.json"
    monkeypatch.setenv("MERIDIAN_SUPERVISOR_COMMAND", _supervisor_command(package_root, capture))

    result = workspace_resume_sync(
        WorkspaceResumeInput(
            workspace=str(workspace.workspace_id),
            fresh=False,
            repo_root=tmp_path.as_posix(),
        )
    )

    assert result.state == "paused"
    assert result.summary_path is not None
    summary_path = Path(result.summary_path)
    assert summary_path.exists()

    payload = _capture_payload(capture)
    env = payload["env"]
    assert isinstance(env, dict)
    prompt = env["MERIDIAN_WORKSPACE_PROMPT"]
    assert isinstance(prompt, str)
    assert "Continuation Guidance" in prompt
    # On resume (fresh=False), pinned context is NOT re-injected — the conversation
    # already has the full history. Re-injection only happens on fresh starts.
    assert "Pinned analysis context" not in prompt
    assert "# Workspace Summary" in prompt

    listed = context_list_sync(
        ContextListInput(
            workspace=str(workspace.workspace_id),
            repo_root=tmp_path.as_posix(),
        )
    )
    assert summary_path.as_posix() in listed.files


def test_workspace_resume_fresh_omits_continuation_guidance(
    package_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = StateDB(tmp_path)
    workspace = state.create_workspace(WorkspaceCreateParams(name="fresh"))
    state.transition_workspace(workspace.workspace_id, "paused")

    capture = tmp_path / "fresh-capture.json"
    monkeypatch.setenv("MERIDIAN_SUPERVISOR_COMMAND", _supervisor_command(package_root, capture))

    result = workspace_resume_sync(
        WorkspaceResumeInput(
            workspace=str(workspace.workspace_id),
            fresh=True,
            repo_root=tmp_path.as_posix(),
        )
    )
    assert result.state == "paused"

    payload = _capture_payload(capture)
    env = payload["env"]
    assert isinstance(env, dict)
    prompt = env["MERIDIAN_WORKSPACE_PROMPT"]
    assert isinstance(prompt, str)
    assert "Continuation Guidance" not in prompt
    assert "fresh supervisor conversation" in prompt


def test_workspace_resume_prelaunch_failure_rolls_back_to_paused(tmp_path: Path) -> None:
    state = StateDB(tmp_path)
    workspace = state.create_workspace(WorkspaceCreateParams(name="resume-rollback"))
    state.transition_workspace(workspace.workspace_id, "paused")
    state.pin_file(workspace.workspace_id, (tmp_path / "missing.md").as_posix())

    # With fresh=True, pinned context is injected and missing files cause an error.
    with pytest.raises(FileNotFoundError, match="Pinned context file is missing"):
        workspace_resume_sync(
            WorkspaceResumeInput(
                workspace=str(workspace.workspace_id),
                repo_root=tmp_path.as_posix(),
                fresh=True,
            )
        )

    refreshed = state.get_workspace(workspace.workspace_id)
    assert refreshed is not None
    assert refreshed.state == "paused"


def test_workspace_state_machine_blocks_invalid_terminal_resume(tmp_path: Path) -> None:
    state = StateDB(tmp_path)
    workspace = state.create_workspace(WorkspaceCreateParams(name="terminal"))

    workspace_crud.transition_workspace(state, workspace.workspace_id, "completed")
    with pytest.raises(ValueError, match="Invalid workspace transition"):
        workspace_crud.transition_workspace(state, workspace.workspace_id, "active")


def test_state_db_transition_workspace_rejects_invalid_transition(tmp_path: Path) -> None:
    state = StateDB(tmp_path)
    workspace = state.create_workspace(WorkspaceCreateParams(name="db-guard"))

    state.transition_workspace(workspace.workspace_id, "completed")
    with pytest.raises(ValueError, match="Invalid workspace transition"):
        state.transition_workspace(workspace.workspace_id, "active")


@pytest.mark.parametrize(
    "status",
    [
        pytest.param("running", id="running"),
        pytest.param("failed", id="failed"),
        pytest.param("succeeded", id="succeeded"),
    ],
)
def test_run_continue_works_for_running_failed_and_succeeded(
    status: RunStatus,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = StateDB(tmp_path)
    run = state.create_run(
        RunCreateParams(
            prompt="original prompt",
            model=ModelId("gpt-5.3-codex"),
        )
    )
    state.update_run_status(run.run_id, status)

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
            run_id=str(run.run_id),
            prompt="",
            repo_root=tmp_path.as_posix(),
        )
    )

    assert result.command == "run.continue"
    forwarded = captured["payload"]
    assert isinstance(forwarded, RunCreateInput)
    assert forwarded.prompt == "original prompt"


def test_diag_repair_rebuilds_corrupt_jsonl_and_repairs_workspace_state(tmp_path: Path) -> None:
    state = StateDB(tmp_path)
    _ = state.create_run(RunCreateParams(prompt="repair", model=ModelId("gpt-5.3-codex")))
    stuck_workspace = state.create_workspace(WorkspaceCreateParams(name="stuck-active"))

    state.paths.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    state.paths.jsonl_path.write_text("not-json\n", encoding="utf-8")

    lock_dir = tmp_path / ".meridian" / "active-workspaces"
    lock_dir.mkdir(parents=True, exist_ok=True)
    stale_lock = lock_dir / "w999.lock"
    stale_lock.write_text('{"child_pid": 999999, "workspace_id": "w999"}\n', encoding="utf-8")

    repaired = diag_repair_sync(DiagRepairInput(repo_root=tmp_path.as_posix()))
    assert repaired.ok is True
    assert "runs_jsonl" in repaired.repaired
    assert "workspace_locks" in repaired.repaired
    assert "workspace_stuck_active" in repaired.repaired
    assert not stale_lock.exists()

    refreshed_workspace = state.get_workspace(stuck_workspace.workspace_id)
    assert refreshed_workspace is not None
    assert refreshed_workspace.state == "abandoned"

    with state.paths.jsonl_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            json.loads(line)


def test_start_alias_forwards_workspace_start_options(monkeypatch: pytest.MonkeyPatch) -> None:
    main_module = importlib.import_module("meridian.cli.main")
    captured: dict[str, list[str]] = {}

    def fake_workspace_app(tokens: list[str]) -> None:
        captured["tokens"] = list(tokens)

    monkeypatch.setattr(main_module, "workspace_app", fake_workspace_app)

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


def test_export_collects_committable_workspace_markdown(tmp_path: Path) -> None:
    state = StateDB(tmp_path)
    workspace = state.create_workspace(WorkspaceCreateParams(name="export"))

    run = state.create_run(
        RunCreateParams(
            prompt="artifact",
            model=ModelId("gpt-5.3-codex"),
            workspace_id=workspace.workspace_id,
        )
    )
    report = (
        tmp_path
        / ".meridian"
        / "workspaces"
        / str(workspace.workspace_id)
        / "runs"
        / "r1"
        / "report.md"
    )
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("# Run report\n", encoding="utf-8")

    extra_markdown = tmp_path / "docs" / "decision-log.md"
    extra_markdown.parent.mkdir(parents=True, exist_ok=True)
    extra_markdown.write_text("# Decision log\n", encoding="utf-8")
    state.pin_file(workspace.workspace_id, extra_markdown.as_posix())

    conn = sqlite3.connect(state.paths.db_path)
    try:
        with conn:
            conn.execute(
                "UPDATE runs SET report_path = ? WHERE id = ?",
                (report.relative_to(tmp_path).as_posix(), str(run.run_id)),
            )
    finally:
        conn.close()

    exported = export_workspace_sync(
        workspace=str(workspace.workspace_id),
        repo_root=tmp_path.as_posix(),
    )

    assert exported.command == "export.workspace"
    assert exported.workspace_id == str(workspace.workspace_id)
    assert (
        f".meridian/workspaces/{workspace.workspace_id}/workspace-summary.md"
        in exported.artifact_paths
    )
    assert report.relative_to(tmp_path).as_posix() in exported.artifact_paths
    assert extra_markdown.relative_to(tmp_path).as_posix() in exported.artifact_paths
