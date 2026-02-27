"""Slice B workspace launch regressions."""

from __future__ import annotations

import json
from pathlib import Path

from meridian.lib.adapters.sqlite import StateDB
from meridian.lib.domain import WorkspaceCreateParams
from meridian.lib.ops.workspace import WorkspaceStartInput, workspace_start_sync
from meridian.lib.types import WorkspaceId
from meridian.lib.workspace.launch import (
    WorkspaceLaunchRequest,
    _build_workspace_env,
    _build_interactive_command,
    build_supervisor_prompt,
    cleanup_orphaned_locks,
)


def test_build_interactive_command_uses_system_prompt_model_and_passthrough(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("MERIDIAN_SUPERVISOR_COMMAND", raising=False)

    request = WorkspaceLaunchRequest(
        workspace_id=WorkspaceId("w42"),
        model="claude-opus-4-6",
        fresh=True,
    )
    prompt = build_supervisor_prompt(request)

    command = _build_interactive_command(
        repo_root=tmp_path,
        request=request,
        prompt=prompt,
        passthrough_args=("--permission-mode", "acceptEdits"),
    )

    assert command[0] == "claude"
    assert "-p" not in command
    assert "--system-prompt" in command
    assert command[command.index("--system-prompt") + 1] == prompt
    assert "--model" in command
    assert command[command.index("--model") + 1] == "claude-opus-4-6"
    assert "--permission-mode" in command
    assert "acceptEdits" in command


def test_build_workspace_env_sanitizes_parent_env_and_keeps_workspace_overrides(
    monkeypatch,
) -> None:
    monkeypatch.setenv("PATH", "/usr/local/bin:/usr/bin")
    monkeypatch.setenv("HOME", "/home/sliceb")
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setenv("MY_SECRET_TOKEN", "do-not-forward")
    monkeypatch.setenv("RANDOM_PARENT_VALUE", "drop-me")
    monkeypatch.setenv("MERIDIAN_DEPTH", "5")

    request = WorkspaceLaunchRequest(
        workspace_id=WorkspaceId("w99"),
        autocompact=80,
    )
    env = _build_workspace_env(request, "workspace prompt")

    assert env["PATH"] == "/usr/local/bin:/usr/bin"
    assert env["HOME"] == "/home/sliceb"
    assert env["LANG"] == "C.UTF-8"
    assert "MY_SECRET_TOKEN" not in env
    assert "RANDOM_PARENT_VALUE" not in env
    assert env["MERIDIAN_WORKSPACE_ID"] == "w99"
    assert env["MERIDIAN_DEPTH"] == "5"
    assert env["MERIDIAN_WORKSPACE_PROMPT"] == "workspace prompt"
    assert env["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"] == "80"


def test_cleanup_orphaned_locks_removes_stale_lock_and_pauses_workspace(tmp_path: Path) -> None:
    state = StateDB(tmp_path)
    workspace = state.create_workspace(WorkspaceCreateParams(name="orphaned"))

    lock_path = tmp_path / ".meridian" / "active-workspaces" / f"{workspace.workspace_id}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        json.dumps(
            {
                "workspace_id": str(workspace.workspace_id),
                "child_pid": 999_999,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    cleaned = cleanup_orphaned_locks(tmp_path)

    assert cleaned == (workspace.workspace_id,)
    assert not lock_path.exists()

    refreshed = state.get_workspace(workspace.workspace_id)
    assert refreshed is not None
    assert refreshed.state == "paused"


def test_workspace_start_dry_run_returns_interactive_command(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("MERIDIAN_SUPERVISOR_COMMAND", raising=False)

    result = workspace_start_sync(
        WorkspaceStartInput(
            repo_root=tmp_path.as_posix(),
            dry_run=True,
        )
    )

    assert result.state == "paused"
    assert result.exit_code == 0
    assert result.message == "Workspace launch dry-run."
    assert result.lock_path is not None
    assert not Path(result.lock_path).exists()
    assert result.command[0] == "claude"
    assert "-p" not in result.command
    assert "--system-prompt" in result.command
