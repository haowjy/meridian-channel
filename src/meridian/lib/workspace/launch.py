"""Workspace supervisor launcher helpers."""

from __future__ import annotations

import json
import os
import shlex
import signal
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from meridian.lib.domain import WorkspaceState
from meridian.lib.exec.spawn import SafeDefaultPermissionResolver
from meridian.lib.harness.adapter import RunParams
from meridian.lib.harness.registry import HarnessRegistry
from meridian.lib.prompt.assembly import resolve_run_defaults
from meridian.lib.types import ModelId, WorkspaceId

_CONTINUATION_GUIDANCE = (
    "You are resuming an existing workspace. Continue from the current state, "
    "preserve prior decisions unless evidence has changed, and avoid duplicating "
    "already-completed work."
)


@dataclass(frozen=True, slots=True)
class WorkspaceLaunchRequest:
    """Inputs for launching one workspace supervisor session."""

    workspace_id: WorkspaceId
    model: str = ""
    fresh: bool = False
    autocompact: int | None = None
    passthrough_args: tuple[str, ...] = ()
    summary_text: str = ""
    pinned_context: str = ""


@dataclass(frozen=True, slots=True)
class WorkspaceLaunchResult:
    """Result metadata from a completed supervisor launch."""

    command: tuple[str, ...]
    exit_code: int
    final_state: WorkspaceState
    lock_path: Path


def workspace_lock_path(repo_root: Path, workspace_id: WorkspaceId) -> Path:
    """Return active workspace lock path for one workspace ID."""

    return repo_root / ".meridian" / "active-workspaces" / f"{workspace_id}.lock"


def build_supervisor_prompt(request: WorkspaceLaunchRequest) -> str:
    """Build launch prompt for workspace start/resume sessions."""

    sections: list[str] = [
        "# Meridian Workspace Session",
        f"Workspace: {request.workspace_id}",
    ]
    if request.summary_text.strip():
        sections.extend(["", "# Workspace Summary", "", request.summary_text.strip()])

    if request.fresh:
        sections.extend(
            [
                "",
                "# Session Mode",
                "",
                "Start a fresh supervisor conversation for this workspace.",
            ]
        )
    else:
        sections.extend(["", "# Continuation Guidance", "", _CONTINUATION_GUIDANCE])

    if request.pinned_context.strip():
        sections.extend(["", "# Re-Injected Pinned Context", "", request.pinned_context.strip()])

    return "\n".join(sections).strip()


def _write_lock(
    *,
    path: Path,
    workspace_id: WorkspaceId,
    command: tuple[str, ...],
    child_pid: int | None,
) -> None:
    payload = {
        "workspace_id": str(workspace_id),
        "parent_pid": os.getpid(),
        "child_pid": child_pid,
        "started_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "command": list(command),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _build_default_harness_command(
    *,
    request: WorkspaceLaunchRequest,
    prompt: str,
    registry: HarnessRegistry,
    passthrough_args: tuple[str, ...],
) -> tuple[str, ...]:
    defaults = resolve_run_defaults(
        request.model,
        (),
        profile=None,
        mode="supervisor",
    )
    harness, _warning = registry.route(defaults.model)
    run = RunParams(
        prompt=prompt,
        model=ModelId(defaults.model),
        skills=defaults.skills,
        extra_args=passthrough_args,
    )
    return tuple(harness.build_command(run, SafeDefaultPermissionResolver()))


def _build_supervisor_command(
    *,
    request: WorkspaceLaunchRequest,
    prompt: str,
    registry: HarnessRegistry,
) -> tuple[str, ...]:
    passthrough = list(request.passthrough_args)
    if request.autocompact is not None:
        passthrough.extend(["--autocompact", str(request.autocompact)])

    override = os.getenv("MERIDIAN_SUPERVISOR_COMMAND", "").strip()
    if override:
        command = [*shlex.split(override), *passthrough]
        if not command:
            raise ValueError("MERIDIAN_SUPERVISOR_COMMAND resolved to an empty command.")
        return tuple(command)

    return _build_default_harness_command(
        request=request,
        prompt=prompt,
        registry=registry,
        passthrough_args=tuple(passthrough),
    )


def launch_supervisor(
    *,
    repo_root: Path,
    registry: HarnessRegistry,
    request: WorkspaceLaunchRequest,
) -> WorkspaceLaunchResult:
    """Launch supervisor process and wait for exit."""

    prompt = build_supervisor_prompt(request)
    command = _build_supervisor_command(request=request, prompt=prompt, registry=registry)
    lock_path = workspace_lock_path(repo_root, request.workspace_id)

    child_env = os.environ.copy()
    child_env["MERIDIAN_WORKSPACE_ID"] = str(request.workspace_id)
    child_env.setdefault("MERIDIAN_DEPTH", "0")
    child_env["MERIDIAN_WORKSPACE_PROMPT"] = prompt
    if request.autocompact is not None:
        child_env["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"] = str(request.autocompact)

    _write_lock(
        path=lock_path,
        workspace_id=request.workspace_id,
        command=command,
        child_pid=None,
    )

    exit_code = 2
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            command,
            cwd=repo_root,
            env=child_env,
            text=True,
        )
        _write_lock(
            path=lock_path,
            workspace_id=request.workspace_id,
            command=command,
            child_pid=process.pid,
        )

        try:
            exit_code = process.wait()
        except KeyboardInterrupt:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
                exit_code = process.wait()
            else:
                exit_code = 130
    except FileNotFoundError:
        exit_code = 2
    finally:
        if lock_path.exists():
            lock_path.unlink()

    final_state: WorkspaceState = "paused" if exit_code in {0, 130, 143} else "abandoned"
    return WorkspaceLaunchResult(
        command=command,
        exit_code=exit_code,
        final_state=final_state,
        lock_path=lock_path,
    )
