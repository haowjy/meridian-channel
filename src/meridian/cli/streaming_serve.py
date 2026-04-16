"""Headless runner for Phase-1 streaming spawn integration."""

from __future__ import annotations

import time
from uuid import uuid4

from meridian.lib.core.domain import Spawn
from meridian.lib.core.types import HarnessId, ModelId
from meridian.lib.harness.registry import get_default_harness_registry
from meridian.lib.launch.streaming_runner import execute_with_streaming
from meridian.lib.ops.runtime import resolve_runtime_root_and_config
from meridian.lib.ops.spawn.plan import ExecutionPolicy, PreparedSpawnPlan, SessionContinuation
from meridian.lib.safety.permissions import resolve_permission_pipeline
from meridian.lib.state import spawn_store
from meridian.lib.state.artifact_store import LocalStore
from meridian.lib.state.paths import resolve_state_paths


async def streaming_serve(
    harness: str,
    prompt: str,
    model: str | None = None,
    agent: str | None = None,
    debug: bool = False,
) -> None:
    """Start a bidirectional spawn and keep it running until completion."""

    normalized_harness = harness.strip().lower()
    if not normalized_harness:
        raise ValueError("harness is required")
    normalized_prompt = prompt.strip()
    if not normalized_prompt:
        raise ValueError("prompt is required")
    normalized_model = model.strip() if model is not None else None
    if model is not None and not normalized_model:
        raise ValueError("model cannot be empty")
    normalized_agent = agent.strip() if agent is not None else None

    try:
        harness_id = HarnessId(normalized_harness)
    except ValueError as exc:
        supported = ", ".join(item.value for item in HarnessId if item != HarnessId.DIRECT)
        raise ValueError(f"unsupported harness '{harness}'. Supported: {supported}") from exc

    repo_root, _ = resolve_runtime_root_and_config(None)
    state_paths = resolve_state_paths(repo_root)
    state_root = state_paths.root_dir
    artifacts = LocalStore(root_dir=state_paths.artifacts_dir)
    start_monotonic = time.monotonic()
    model_name = normalized_model or "unknown"
    agent_name = normalized_agent or "unknown"
    spawn_id = spawn_store.start_spawn(
        state_root,
        chat_id=str(uuid4()),
        model=model_name,
        agent=agent_name,
        harness=harness_id.value,
        kind="streaming",
        prompt=normalized_prompt,
        launch_mode="foreground",
        status="queued",
    )

    permission_config, permission_resolver = resolve_permission_pipeline(
        sandbox=None,
        approval="default",
    )
    plan = PreparedSpawnPlan(
        model=model_name,
        harness_id=harness_id.value,
        prompt=normalized_prompt,
        agent_name=normalized_agent if normalized_agent else None,
        skills=(),
        skill_paths=(),
        reference_files=(),
        template_vars={},
        mcp_tools=(),
        session_agent=agent_name,
        session_agent_path="",
        session=SessionContinuation(),
        execution=ExecutionPolicy(
            permission_config=permission_config,
            permission_resolver=permission_resolver,
        ),
        cli_command=(),
    )
    spawn = Spawn(
        spawn_id=spawn_id,
        prompt=normalized_prompt,
        model=ModelId(normalized_model or ""),
        status="queued",
    )

    output_path = state_root / "spawns" / str(spawn_id) / "output.jsonl"
    socket_path = state_root / "spawns" / str(spawn_id) / "control.sock"

    print(f"Started spawn {spawn_id} (harness={harness_id.value})")
    print(f"Control socket: {socket_path}")
    print(f"Events: {output_path}")

    outcome_status = "failed"
    outcome_exit_code = 1
    failure_message: str | None = None
    try:
        outcome_exit_code = await execute_with_streaming(
            run=spawn,
            plan=plan,
            repo_root=repo_root,
            state_root=state_root,
            artifacts=artifacts,
            registry=get_default_harness_registry(),
            cwd=repo_root,
            debug=debug,
        )
        row = spawn_store.get_spawn(state_root, spawn_id)
        if row is not None:
            outcome_status = row.status
            if row.exit_code is not None:
                outcome_exit_code = row.exit_code
            failure_message = row.error
        elif outcome_exit_code == 0:
            outcome_status = "succeeded"
    except Exception as exc:
        failure_message = str(exc)
        spawn_store.finalize_spawn(
            state_root,
            spawn_id,
            status="failed",
            exit_code=outcome_exit_code,
            origin="launcher",
            duration_secs=max(0.0, time.monotonic() - start_monotonic),
            error=failure_message,
        )
        raise
    finally:
        print(f"Stopped spawn {spawn_id} (status={outcome_status}, exit={outcome_exit_code})")
