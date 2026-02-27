"""Workspace supervisor launcher helpers."""

from __future__ import annotations

import json
import logging
import os
import shlex
import signal
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from meridian.lib.config._paths import resolve_repo_root
from meridian.lib.config.agent import AgentProfile, load_agent_profile
from meridian.lib.config.routing import route_model
from meridian.lib.config.settings import load_config
from meridian.lib.domain import WorkspaceState
from meridian.lib.exec.spawn import HARNESS_ENV_PASS_THROUGH, sanitize_child_env
from meridian.lib.prompt.assembly import load_skill_contents, resolve_run_defaults
from meridian.lib.safety.permissions import (
    _permission_tier_from_profile,
    _warn_profile_tier_escalation,
    build_permission_config,
    permission_flags_for_harness,
)
from meridian.lib.state.db import open_connection, resolve_state_paths
from meridian.lib.types import HarnessId, ModelId, WorkspaceId

_CONTINUATION_GUIDANCE = (
    "You are resuming an existing workspace. Continue from the current state, "
    "preserve prior decisions unless evidence has changed, and avoid duplicating "
    "already-completed work."
)
logger = logging.getLogger(__name__)


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
    dry_run: bool = False


@dataclass(frozen=True, slots=True)
class WorkspaceLaunchResult:
    """Result metadata from a completed supervisor launch."""

    command: tuple[str, ...]
    exit_code: int
    final_state: WorkspaceState
    lock_path: Path


def workspace_lock_path(repo_root: Path, workspace_id: WorkspaceId) -> Path:
    """Return active workspace lock path for one workspace ID."""

    return resolve_state_paths(repo_root).active_workspaces_dir / f"{workspace_id}.lock"


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


def _build_interactive_command(
    *,
    repo_root: Path | None = None,
    request: WorkspaceLaunchRequest,
    prompt: str,
    passthrough_args: tuple[str, ...],
) -> tuple[str, ...]:
    """Build interactive CLI command for workspace sessions."""

    override = os.getenv("MERIDIAN_SUPERVISOR_COMMAND", "").strip()
    if override:
        command = [*shlex.split(override), *passthrough_args]
        if not command:
            raise ValueError("MERIDIAN_SUPERVISOR_COMMAND resolved to an empty command.")
        return tuple(command)

    resolved_root = resolve_repo_root(repo_root)
    config = load_config(resolved_root)
    profile: AgentProfile | None = None
    configured_profile = config.supervisor_agent.strip()
    if configured_profile:
        try:
            profile = load_agent_profile(
                configured_profile,
                repo_root=resolved_root,
                search_paths=config.search_paths,
            )
        except FileNotFoundError:
            profile = None

    defaults = resolve_run_defaults(
        request.model,
        (),
        profile=profile,
    )
    model = ModelId(defaults.model)
    supervisor_harness = _resolve_supervisor_harness(model=model)

    prompt_with_profile_skills = prompt
    if profile is not None and defaults.skills:
        from meridian.lib.config.skill_registry import SkillRegistry

        registry = SkillRegistry(
            repo_root=resolved_root,
            search_paths=config.search_paths,
            readonly=True,
        )
        manifests = registry.list()
        available_skills = {item.name for item in manifests}
        skill_names = tuple(
            skill_name for skill_name in defaults.skills if skill_name in available_skills
        )
        missing_skills = tuple(
            skill_name for skill_name in defaults.skills if skill_name not in available_skills
        )
        if missing_skills:
            logger.warning(
                "Skipping unavailable supervisor profile skills: %s.",
                ", ".join(missing_skills),
            )
        loaded_skills = load_skill_contents(registry, skill_names)
        if loaded_skills:
            sections = [prompt_with_profile_skills, "", "# Supervisor Skills"]
            for skill in loaded_skills:
                sections.extend(["", f"## Skill: {skill.name}", "", skill.content.strip()])
            prompt_with_profile_skills = "\n".join(sections).strip()

    command: list[str] = [
        "claude",
        "--system-prompt",
        prompt_with_profile_skills,
        "--model",
        str(model),
    ]
    resolved_tier = _resolve_permission_tier_for_profile(
        profile=profile,
        default_tier=config.default_permission_tier,
    )
    _warn_profile_tier_escalation(
        profile=profile,
        inferred_tier=resolved_tier,
        default_tier=config.default_permission_tier,
        warning_logger=logger,
    )
    permission_config = build_permission_config(
        resolved_tier,
        unsafe=False,
        default_tier=config.default_permission_tier,
    )
    command.extend(
        permission_flags_for_harness(
            supervisor_harness,
            permission_config,
        )
    )
    command.extend(passthrough_args)
    return tuple(command)


def _build_supervisor_command(
    *,
    repo_root: Path,
    request: WorkspaceLaunchRequest,
    prompt: str,
) -> tuple[str, ...]:
    passthrough = list(request.passthrough_args)
    if request.autocompact is not None:
        passthrough.extend(["--autocompact", str(request.autocompact)])

    return _build_interactive_command(
        repo_root=repo_root,
        request=request,
        prompt=prompt,
        passthrough_args=tuple(passthrough),
    )


def _resolve_permission_tier_for_profile(
    *,
    profile: AgentProfile | None,
    default_tier: str,
) -> str:
    sandbox_value = profile.sandbox if profile is not None else None
    inferred_tier = _permission_tier_from_profile(sandbox_value)
    if inferred_tier is not None:
        return inferred_tier

    if profile is not None and sandbox_value is not None and sandbox_value.strip():
        logger.warning(
            "Agent profile '%s' has unsupported sandbox '%s'; "
            "falling back to default permission tier '%s'.",
            profile.name,
            sandbox_value.strip(),
            default_tier,
        )
    return default_tier


def _resolve_supervisor_harness(*, model: ModelId) -> HarnessId:
    decision = route_model(str(model), mode="harness")
    harness_id = decision.harness_id
    if harness_id == HarnessId("claude"):
        return harness_id

    message = (
        "Workspace supervisor only supports Claude harness models. "
        f"Model '{model}' routes to harness '{harness_id}'."
    )
    if decision.warning:
        message = f"{message} {decision.warning}"
    raise ValueError(message)


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but owned by another user; assume it's alive.
        return True
    except OSError:
        return False
    return True


def _transition_orphaned_workspace_states(
    repo_root: Path,
    workspace_ids: tuple[WorkspaceId, ...],
) -> None:
    if not workspace_ids:
        return

    db_path = resolve_state_paths(repo_root).db_path
    conn = open_connection(db_path)
    try:
        with conn:
            for workspace_id in workspace_ids:
                conn.execute(
                    """
                    UPDATE workspaces
                    SET status = 'paused',
                        last_activity_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
                    WHERE id = ? AND status = 'active'
                    """,
                    (str(workspace_id),),
                )
    finally:
        conn.close()


def cleanup_orphaned_locks(repo_root: Path) -> tuple[WorkspaceId, ...]:
    """Remove stale workspace locks and mark orphaned active workspaces paused."""

    lock_dir = resolve_state_paths(repo_root).active_workspaces_dir
    if not lock_dir.exists():
        return ()

    orphaned: list[WorkspaceId] = []
    for lock_file in sorted(lock_dir.glob("*.lock")):
        if not lock_file.is_file():
            continue

        workspace_id = WorkspaceId(lock_file.stem)
        child_pid = 0
        try:
            parsed = json.loads(lock_file.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                payload = cast("dict[str, object]", parsed)
                raw_workspace_id = payload.get("workspace_id")
                if isinstance(raw_workspace_id, str) and raw_workspace_id.strip():
                    workspace_id = WorkspaceId(raw_workspace_id.strip())
                raw_child_pid = payload.get("child_pid")
                if isinstance(raw_child_pid, int):
                    child_pid = raw_child_pid
        except (OSError, json.JSONDecodeError, TypeError):
            pass

        if child_pid > 0 and _pid_exists(child_pid):
            continue

        lock_file.unlink(missing_ok=True)
        orphaned.append(workspace_id)

    deduped = tuple(
        WorkspaceId(workspace_id)
        for workspace_id in sorted({str(workspace_id) for workspace_id in orphaned})
    )
    _transition_orphaned_workspace_states(repo_root, deduped)
    return deduped


def _build_workspace_env(request: WorkspaceLaunchRequest, prompt: str) -> dict[str, str]:
    env_overrides = {
        "MERIDIAN_WORKSPACE_ID": str(request.workspace_id),
        "MERIDIAN_DEPTH": os.environ.get("MERIDIAN_DEPTH", "0"),
        "MERIDIAN_WORKSPACE_PROMPT": prompt,
    }
    if request.autocompact is not None:
        env_overrides["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"] = str(request.autocompact)

    return sanitize_child_env(
        base_env=os.environ,
        env_overrides=env_overrides,
        pass_through=HARNESS_ENV_PASS_THROUGH,
    )


def launch_supervisor(
    *,
    repo_root: Path,
    request: WorkspaceLaunchRequest,
) -> WorkspaceLaunchResult:
    """Launch supervisor process and wait for exit."""

    prompt = build_supervisor_prompt(request)
    command = _build_supervisor_command(repo_root=repo_root, request=request, prompt=prompt)
    lock_path = workspace_lock_path(repo_root, request.workspace_id)
    child_env = _build_workspace_env(request, prompt)

    if request.dry_run:
        return WorkspaceLaunchResult(
            command=command,
            exit_code=0,
            final_state="paused",
            lock_path=lock_path,
        )

    if sys.stdin.isatty():
        # execvp replaces this process entirely on success, so:
        # - The lock file is intentionally left behind (PID stays the same since
        #   exec replaces the process image). cleanup_orphaned_locks() on the
        #   next CLI invocation will remove it after the child exits.
        # - The caller's post-launch state transitions (in workspace_start_sync /
        #   workspace_resume_sync) will never execute. The workspace row remains
        #   in its pre-launch state until the next cleanup cycle.
        _write_lock(
            path=lock_path,
            workspace_id=request.workspace_id,
            command=command,
            child_pid=os.getpid(),
        )
        saved_cwd = os.getcwd()
        os.environ.update(child_env)
        os.chdir(repo_root)
        try:
            os.execvp(command[0], list(command))
        except OSError:
            # execvp failed — restore environment and cwd so the caller
            # can continue without corrupted process state.
            for key in child_env:
                if key not in os.environ:
                    continue
                if key.startswith("MERIDIAN_") or key == "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE":
                    os.environ.pop(key, None)
            os.chdir(saved_cwd)
            lock_path.unlink(missing_ok=True)
            return WorkspaceLaunchResult(
                command=command,
                exit_code=2,
                final_state="abandoned",
                lock_path=lock_path,
            )

    exit_code = 2
    process: subprocess.Popen[str] | None = None
    try:
        _write_lock(
            path=lock_path,
            workspace_id=request.workspace_id,
            command=command,
            child_pid=None,
        )
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
