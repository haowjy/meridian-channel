"""Run execution helpers shared by sync and async run handlers."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Protocol, cast

import structlog

from meridian.lib.domain import RunCreateParams
from meridian.lib.exec.spawn import execute_with_finalization
from meridian.lib.exec.terminal import TerminalEventFilter, resolve_visible_categories
from meridian.lib.ops._runtime import OperationRuntime, build_runtime, resolve_workspace_id
from meridian.lib.safety.budget import Budget
from meridian.lib.safety.permissions import PermissionConfig, TieredPermissionResolver
from meridian.lib.safety.redaction import SecretSpec, secrets_env_overrides
from meridian.lib.state.db import resolve_state_paths
from meridian.lib.types import ModelId, RunId

from ._run_models import RunActionOutput, RunCreateInput
from ._run_query import _read_run_row

_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()
logger = structlog.get_logger(__name__)


class _PreparedCreateLike(Protocol):
    model: str
    harness_id: str
    warning: str | None
    composed_prompt: str
    skills: tuple[str, ...]
    reference_files: tuple[str, ...]
    template_vars: dict[str, str]
    report_path: str
    mcp_tools: tuple[str, ...]
    agent_name: str | None
    cli_command: tuple[str, ...]
    permission_config: PermissionConfig
    budget: Budget | None
    guardrails: tuple[str, ...]
    secrets: tuple[SecretSpec, ...]


def _read_non_negative_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if value < 0:
        raise ValueError(f"{name} must be >= 0.")
    return value


def _depth_limits(max_depth: int) -> tuple[int, int]:
    current_depth = _read_non_negative_int_env("MERIDIAN_DEPTH", 0)
    if max_depth < 0:
        raise ValueError("max_depth must be >= 0.")
    return current_depth, max_depth


def _emit_subrun_event(payload: dict[str, Any]) -> None:
    if _read_non_negative_int_env("MERIDIAN_DEPTH", 0) <= 0:
        return
    event_payload = dict(payload)
    event_payload["v"] = 1
    parent_run_id = os.getenv("MERIDIAN_PARENT_RUN_ID", "").strip()
    event_payload["parent"] = parent_run_id or None
    event_payload["ts"] = time.time()
    print(json.dumps(event_payload, separators=(",", ":")), file=sys.stdout, flush=True)


def _depth_exceeded_output(current_depth: int, max_depth: int) -> RunActionOutput:
    return RunActionOutput(
        command="run.create",
        status="failed",
        message=f"Max agent depth ({max_depth}) reached. Complete this task directly.",
        error="max_depth_exceeded",
        current_depth=current_depth,
        max_depth=max_depth,
    )


def _run_child_env(
    workspace_id: str | None,
    secrets: tuple[SecretSpec, ...],
    parent_run_id: str | None = None,
) -> dict[str, str]:
    # Preserve Meridian run context across nesting without forwarding unrelated
    # parent process environment variables.
    child_env = {key: value for key, value in os.environ.items() if key.startswith("MERIDIAN_")}
    current_depth = _read_non_negative_int_env("MERIDIAN_DEPTH", 0)
    child_env["MERIDIAN_DEPTH"] = str(current_depth + 1)
    if workspace_id is not None:
        child_env["MERIDIAN_WORKSPACE_ID"] = workspace_id
    if parent_run_id is None:
        child_env.pop("MERIDIAN_PARENT_RUN_ID", None)
    else:
        normalized_parent = parent_run_id.strip()
        if normalized_parent:
            child_env["MERIDIAN_PARENT_RUN_ID"] = normalized_parent
        else:
            child_env.pop("MERIDIAN_PARENT_RUN_ID", None)
    child_env.update(secrets_env_overrides(secrets))
    return child_env


def _workspace_spend_usd(repo_root: Path, workspace_id: str | None) -> float:
    if workspace_id is None:
        return 0.0

    db_path = resolve_state_paths(repo_root).db_path
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT total_cost_usd FROM workspaces WHERE id = ?",
            (workspace_id,),
        ).fetchone()
        if row is not None and row["total_cost_usd"] is not None:
            return float(row["total_cost_usd"])

        fallback = conn.execute(
            "SELECT COALESCE(SUM(total_cost_usd), 0.0) AS spent FROM runs WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchone()
        if fallback is None:
            return 0.0
        return float(fallback["spent"] or 0.0)
    finally:
        conn.close()


def _execute_run_blocking(
    *,
    payload: RunCreateInput,
    prepared: _PreparedCreateLike,
    runtime: OperationRuntime,
) -> RunActionOutput:
    workspace_id = resolve_workspace_id(payload.workspace)

    run = runtime.run_store_sync.create(
        RunCreateParams(
            prompt=prepared.composed_prompt,
            model=ModelId(prepared.model),
            workspace_id=workspace_id,
        )
    )
    current_depth = _read_non_negative_int_env("MERIDIAN_DEPTH", 0)
    run_start_event: dict[str, Any] = {
        "t": "meridian.run.start",
        "id": str(run.run_id),
        "model": prepared.model,
        "d": current_depth,
    }
    if prepared.agent_name is not None:
        run_start_event["agent"] = prepared.agent_name
    _emit_subrun_event(run_start_event)

    started = time.monotonic()
    workspace_id_str = str(workspace_id) if workspace_id is not None else None
    event_observer = None
    if not payload.stream:
        event_filter = TerminalEventFilter(
            visible_categories=resolve_visible_categories(
                verbose=payload.verbose,
                quiet=payload.quiet,
                config=runtime.config.output,
            ),
            root_depth=_read_non_negative_int_env("MERIDIAN_DEPTH", 0),
        )
        event_observer = event_filter.observe

    exit_code = asyncio.run(
        execute_with_finalization(
            run,
            state=runtime.state,
            artifacts=runtime.artifacts,
            registry=runtime.harness_registry,
            permission_resolver=TieredPermissionResolver(prepared.permission_config),
            permission_config=prepared.permission_config,
            cwd=runtime.repo_root,
            timeout_seconds=payload.timeout_secs,
            kill_grace_seconds=runtime.config.kill_grace_seconds,
            skills=prepared.skills,
            agent=prepared.agent_name,
            mcp_tools=prepared.mcp_tools,
            env_overrides=_run_child_env(
                workspace_id_str,
                prepared.secrets,
                str(run.run_id),
            ),
            budget=prepared.budget,
            workspace_spent_usd=_workspace_spend_usd(runtime.repo_root, workspace_id_str),
            max_retries=runtime.config.max_retries,
            retry_backoff_seconds=runtime.config.retry_backoff_seconds,
            guardrails=tuple(Path(item) for item in prepared.guardrails),
            guardrail_timeout_seconds=runtime.config.guardrail_timeout_seconds,
            secrets=prepared.secrets,
            event_observer=event_observer,
            stream_stdout_to_terminal=payload.stream,
            stream_stderr_to_terminal=payload.stream or payload.verbose,
        )
    )
    duration = time.monotonic() - started

    row = _read_run_row(runtime.repo_root, str(run.run_id))
    status = "failed"
    if row is not None:
        status = str(row["status"])
    done_secs = duration
    tokens_total: int | None = None
    if row is not None:
        row_duration = cast("float | None", row["duration_secs"])
        if row_duration is not None:
            done_secs = row_duration
        input_tokens = cast("int | None", row["input_tokens"])
        output_tokens = cast("int | None", row["output_tokens"])
        if input_tokens is not None and output_tokens is not None:
            tokens_total = input_tokens + output_tokens
    _emit_subrun_event(
        {
            "t": "meridian.run.done",
            "id": str(run.run_id),
            "exit": exit_code,
            "secs": done_secs,
            "tok": tokens_total,
            "d": current_depth,
        }
    )

    return RunActionOutput(
        command="run.create",
        status=status,
        run_id=str(run.run_id),
        message="Run completed.",
        model=prepared.model,
        harness_id=prepared.harness_id,
        warning=prepared.warning,
        agent=prepared.agent_name,
        skills=prepared.skills,
        reference_files=prepared.reference_files,
        template_vars=prepared.template_vars,
        report_path=prepared.report_path,
        cli_command=prepared.cli_command,
        exit_code=exit_code,
        duration_secs=duration,
    )


async def _execute_run_non_blocking(
    *,
    run_id: RunId,
    repo_root: Path,
    timeout_secs: float | None,
    skills: tuple[str, ...],
    agent_name: str | None,
    mcp_tools: tuple[str, ...],
    permission_config: PermissionConfig,
    budget: Budget | None,
    guardrails: tuple[str, ...],
    secrets: tuple[SecretSpec, ...],
) -> None:
    runtime = build_runtime(str(repo_root))
    run = await runtime.run_store.get(run_id)
    if run is None:
        return

    await execute_with_finalization(
        run,
        state=runtime.state,
        artifacts=runtime.artifacts,
        registry=runtime.harness_registry,
        permission_resolver=TieredPermissionResolver(permission_config),
        permission_config=permission_config,
        cwd=runtime.repo_root,
        timeout_seconds=timeout_secs,
        kill_grace_seconds=runtime.config.kill_grace_seconds,
        skills=skills,
        agent=agent_name,
        mcp_tools=mcp_tools,
        env_overrides=_run_child_env(
            str(run.workspace_id) if run.workspace_id is not None else None,
            secrets,
            str(run.run_id),
        ),
        budget=budget,
        workspace_spent_usd=_workspace_spend_usd(
            runtime.repo_root,
            str(run.workspace_id) if run.workspace_id is not None else None,
        ),
        max_retries=runtime.config.max_retries,
        retry_backoff_seconds=runtime.config.retry_backoff_seconds,
        guardrails=tuple(Path(item) for item in guardrails),
        guardrail_timeout_seconds=runtime.config.guardrail_timeout_seconds,
        secrets=secrets,
    )


def _track_task(task: asyncio.Task[None]) -> None:
    _BACKGROUND_TASKS.add(task)

    def _cleanup(done: asyncio.Task[None]) -> None:
        try:
            done.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Background run task failed.")
        finally:
            _BACKGROUND_TASKS.discard(done)

    task.add_done_callback(_cleanup)
