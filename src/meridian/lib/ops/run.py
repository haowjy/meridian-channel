"""Run operations used by CLI, MCP, and DirectAdapter surfaces."""

from __future__ import annotations

import asyncio
import sqlite3
import time
from dataclasses import replace
from pathlib import Path
from typing import cast

from meridian.lib.domain import RunCreateParams
from meridian.lib.exec.spawn import execute_with_finalization
from meridian.lib.ops._runtime import (
    build_runtime_from_root_and_config,
    resolve_runtime_root_and_config,
    resolve_workspace_id,
)
from meridian.lib.ops.registry import OperationSpec, operation
from meridian.lib.safety.permissions import (
    build_permission_config,
    validate_permission_config_for_harness,
)
from meridian.lib.state.db import resolve_state_paths
from meridian.lib.types import ModelId

from . import _run_execute as _run_execute_module
from . import _run_prepare as _run_prepare_module
from ._run_execute import (
    _BACKGROUND_TASKS,
    _depth_exceeded_output,
    _depth_limits,
    _emit_subrun_event,
    _execute_run_blocking,
    _execute_run_non_blocking,
    _read_non_negative_int_env,
    _run_child_env,
    _track_task,
    _workspace_spend_usd,
    logger,
)
from ._run_models import (
    _empty_template_vars,
    RunActionOutput,
    RunContinueInput,
    RunCreateInput,
    RunDetailOutput,
    RunListEntry,
    RunListFilters,
    RunListInput,
    RunListOutput,
    RunRetryInput,
    RunShowInput,
    RunWaitInput,
)
from ._run_prepare import (
    _CreateRuntimeView,
    _PreparedCreate,
    _build_create_payload,
    _looks_like_alias_identifier,
    _merge_warnings,
    _normalize_skill_flags,
    _validate_create_input,
    _validate_requested_model,
)
from ._run_query import (
    _build_run_list_query,
    _detail_from_row,
    _read_files_touched,
    _read_report_text,
    _read_run_row,
)


def run_create_sync(payload: RunCreateInput) -> RunActionOutput:
    _run_prepare_module.build_permission_config = build_permission_config
    _run_prepare_module.validate_permission_config_for_harness = validate_permission_config_for_harness
    _run_prepare_module.logger = logger
    _run_execute_module.execute_with_finalization = execute_with_finalization
    _run_execute_module.logger = logger

    payload, preflight_warning = _validate_create_input(payload)

    runtime = None
    if not payload.dry_run:
        resolved_root, config = resolve_runtime_root_and_config(payload.repo_root)
        current_depth, max_depth = _depth_limits(config.max_depth)
        if current_depth >= max_depth:
            return _depth_exceeded_output(current_depth, max_depth)
        runtime = build_runtime_from_root_and_config(resolved_root, config)

    prepared = _build_create_payload(payload, runtime=runtime, preflight_warning=preflight_warning)
    if payload.dry_run:
        return RunActionOutput(
            command="run.create",
            status="dry-run",
            model=prepared.model,
            harness_id=prepared.harness_id,
            warning=prepared.warning,
            agent=prepared.agent_name,
            skills=prepared.skills,
            reference_files=prepared.reference_files,
            template_vars=prepared.template_vars,
            report_path=prepared.report_path,
            composed_prompt=prepared.composed_prompt,
            cli_command=prepared.cli_command,
            message="Dry run complete.",
        )

    if runtime is None:
        raise RuntimeError("Run runtime was not initialized.")
    return _execute_run_blocking(payload=payload, prepared=prepared, runtime=runtime)


async def run_create(payload: RunCreateInput) -> RunActionOutput:
    _run_prepare_module.build_permission_config = build_permission_config
    _run_prepare_module.validate_permission_config_for_harness = validate_permission_config_for_harness
    _run_prepare_module.logger = logger
    _run_execute_module.execute_with_finalization = execute_with_finalization
    _run_execute_module.logger = logger

    payload, preflight_warning = _validate_create_input(payload)

    runtime = None
    if not payload.dry_run:
        resolved_root, config = resolve_runtime_root_and_config(payload.repo_root)
        current_depth, max_depth = _depth_limits(config.max_depth)
        if current_depth >= max_depth:
            return _depth_exceeded_output(current_depth, max_depth)
        runtime = build_runtime_from_root_and_config(resolved_root, config)

    prepared = _build_create_payload(payload, runtime=runtime, preflight_warning=preflight_warning)
    if payload.dry_run:
        return RunActionOutput(
            command="run.create",
            status="dry-run",
            model=prepared.model,
            harness_id=prepared.harness_id,
            warning=prepared.warning,
            agent=prepared.agent_name,
            skills=prepared.skills,
            reference_files=prepared.reference_files,
            template_vars=prepared.template_vars,
            report_path=prepared.report_path,
            composed_prompt=prepared.composed_prompt,
            cli_command=prepared.cli_command,
            message="Dry run complete.",
        )

    if runtime is None:
        raise RuntimeError("Run runtime was not initialized.")
    workspace_id = resolve_workspace_id(payload.workspace)
    run = await runtime.run_store.create(
        RunCreateParams(
            prompt=prepared.composed_prompt,
            model=ModelId(prepared.model),
            workspace_id=workspace_id,
        )
    )
    current_depth = _read_non_negative_int_env("MERIDIAN_DEPTH", 0)
    run_start_event: dict[str, object] = {
        "t": "meridian.run.start",
        "id": str(run.run_id),
        "model": prepared.model,
        "d": current_depth,
    }
    if prepared.agent_name is not None:
        run_start_event["agent"] = prepared.agent_name
    _emit_subrun_event(run_start_event)

    task = asyncio.create_task(
        _execute_run_non_blocking(
            run_id=run.run_id,
            repo_root=runtime.repo_root,
            timeout_secs=payload.timeout_secs,
            skills=prepared.skills,
            agent_name=prepared.agent_name,
            mcp_tools=prepared.mcp_tools,
            permission_config=prepared.permission_config,
            budget=prepared.budget,
            guardrails=prepared.guardrails,
            secrets=prepared.secrets,
        )
    )
    _track_task(task)

    return RunActionOutput(
        command="run.create",
        status="running",
        run_id=str(run.run_id),
        message="Run started. Use run_show or run_wait for completion.",
        model=prepared.model,
        harness_id=prepared.harness_id,
        warning=prepared.warning,
        agent=prepared.agent_name,
        skills=prepared.skills,
        reference_files=prepared.reference_files,
        template_vars=prepared.template_vars,
        report_path=prepared.report_path,
        cli_command=prepared.cli_command,
    )


def run_list_sync(payload: RunListInput) -> RunListOutput:
    repo_root, _ = resolve_runtime_root_and_config(payload.repo_root)
    filters = RunListFilters(
        model=(
            payload.model.strip()
            if payload.model is not None and payload.model.strip()
            else None
        ),
        workspace=(
            payload.workspace.strip()
            if payload.workspace is not None and payload.workspace.strip()
            else None
        ),
        no_workspace=payload.no_workspace,
        status=payload.status,
        failed=payload.failed,
        limit=payload.limit,
    )
    query, params = _build_run_list_query(filters)

    db_path = resolve_state_paths(repo_root).db_path
    if not db_path.is_file():
        return RunListOutput(runs=())

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(query, tuple(params)).fetchall()
    finally:
        conn.close()

    return RunListOutput(
        runs=tuple(
            RunListEntry(
                run_id=str(row["id"]),
                status=str(row["status"]),
                model=str(row["model"]),
                workspace_id=cast("str | None", row["workspace_id"]),
                duration_secs=cast("float | None", row["duration_secs"]),
                cost_usd=cast("float | None", row["total_cost_usd"]),
            )
            for row in rows
        )
    )


async def run_list(payload: RunListInput) -> RunListOutput:
    return await asyncio.to_thread(run_list_sync, payload)


def run_show_sync(payload: RunShowInput) -> RunDetailOutput:
    repo_root, _ = resolve_runtime_root_and_config(payload.repo_root)
    row = _read_run_row(repo_root, payload.run_id)
    if row is None:
        raise ValueError(f"Run '{payload.run_id}' not found")
    return _detail_from_row(
        repo_root=repo_root,
        row=row,
        include_report=payload.include_report,
        include_files=payload.include_files,
    )


async def run_show(payload: RunShowInput) -> RunDetailOutput:
    return await asyncio.to_thread(run_show_sync, payload)


def _run_is_terminal(status: str) -> bool:
    return status not in {"queued", "running"}


def run_wait_sync(payload: RunWaitInput) -> RunDetailOutput:
    repo_root, config = resolve_runtime_root_and_config(payload.repo_root)
    timeout_secs = (
        payload.timeout_secs if payload.timeout_secs is not None else config.wait_timeout_seconds
    )
    deadline = time.monotonic() + max(timeout_secs, 0.0)
    poll = (
        payload.poll_interval_secs
        if payload.poll_interval_secs is not None
        # run.wait polling is a read-side retry loop, so we intentionally reuse
        # retry_backoff_seconds as the default cadence when no poll interval is set.
        else config.retry_backoff_seconds
    )
    if poll <= 0:
        poll = config.retry_backoff_seconds

    while True:
        row = _read_run_row(repo_root, payload.run_id)
        if row is None:
            raise ValueError(f"Run '{payload.run_id}' not found")

        status = str(row["status"])
        if _run_is_terminal(status):
            return _detail_from_row(
                repo_root=repo_root,
                row=row,
                include_report=payload.include_report,
                include_files=payload.include_files,
            )

        if time.monotonic() >= deadline:
            raise TimeoutError(f"Timed out waiting for run '{payload.run_id}'")
        time.sleep(poll)


async def run_wait(payload: RunWaitInput) -> RunDetailOutput:
    return await asyncio.to_thread(run_wait_sync, payload)


def _prompt_for_follow_up(payload_run_id: str, repo_root: Path, prompt: str | None) -> str:
    if prompt is not None and prompt.strip():
        return prompt

    row = _read_run_row(repo_root, payload_run_id)
    if row is None:
        raise ValueError(f"Run '{payload_run_id}' not found")
    existing_prompt = str(row["prompt"] or "").strip()
    if not existing_prompt:
        raise ValueError(f"Run '{payload_run_id}' has no stored prompt")
    return existing_prompt


def _with_command(result: RunActionOutput, command: str) -> RunActionOutput:
    return replace(result, command=command)


def run_continue_sync(payload: RunContinueInput) -> RunActionOutput:
    repo_root, _ = resolve_runtime_root_and_config(payload.repo_root)
    derived_prompt = _prompt_for_follow_up(payload.run_id, repo_root, payload.prompt)
    # Note: agent is not forwarded from the original run, so
    # agent_explicitly_requested will be False and permission-escalation
    # warnings won't fire.  This is acceptable for continue/retry since
    # the user already approved the original run's permissions.
    create_input = RunCreateInput(
        prompt=derived_prompt,
        model=payload.model,
        repo_root=payload.repo_root,
        timeout_secs=payload.timeout_secs,
    )
    result = run_create_sync(create_input)
    return _with_command(result, "run.continue")


async def run_continue(payload: RunContinueInput) -> RunActionOutput:
    return await asyncio.to_thread(run_continue_sync, payload)


def run_retry_sync(payload: RunRetryInput) -> RunActionOutput:
    repo_root, _ = resolve_runtime_root_and_config(payload.repo_root)
    derived_prompt = _prompt_for_follow_up(payload.run_id, repo_root, payload.prompt)
    create_input = RunCreateInput(
        prompt=derived_prompt,
        model=payload.model,
        repo_root=payload.repo_root,
        timeout_secs=payload.timeout_secs,
    )
    result = run_create_sync(create_input)
    return _with_command(result, "run.retry")


async def run_retry(payload: RunRetryInput) -> RunActionOutput:
    return await asyncio.to_thread(run_retry_sync, payload)


operation(
    OperationSpec[RunCreateInput, RunActionOutput](
        name="run.create",
        handler=run_create,
        sync_handler=run_create_sync,
        input_type=RunCreateInput,
        output_type=RunActionOutput,
        cli_group="run",
        cli_name="create",
        mcp_name="run_create",
        description="Create and start a run.",
    )
)

operation(
    OperationSpec[RunListInput, RunListOutput](
        name="run.list",
        handler=run_list,
        sync_handler=run_list_sync,
        input_type=RunListInput,
        output_type=RunListOutput,
        cli_group="run",
        cli_name="list",
        mcp_name="run_list",
        description="List runs with optional filters.",
    )
)

operation(
    OperationSpec[RunShowInput, RunDetailOutput](
        name="run.show",
        handler=run_show,
        sync_handler=run_show_sync,
        input_type=RunShowInput,
        output_type=RunDetailOutput,
        cli_group="run",
        cli_name="show",
        mcp_name="run_show",
        description="Show run details.",
    )
)

operation(
    OperationSpec[RunContinueInput, RunActionOutput](
        name="run.continue",
        handler=run_continue,
        sync_handler=run_continue_sync,
        input_type=RunContinueInput,
        output_type=RunActionOutput,
        cli_group="run",
        cli_name="continue",
        mcp_name="run_continue",
        description="Continue a previous run.",
    )
)

operation(
    OperationSpec[RunRetryInput, RunActionOutput](
        name="run.retry",
        handler=run_retry,
        sync_handler=run_retry_sync,
        input_type=RunRetryInput,
        output_type=RunActionOutput,
        cli_group="run",
        cli_name="retry",
        mcp_name="run_retry",
        description="Retry a previous run.",
    )
)

operation(
    OperationSpec[RunWaitInput, RunDetailOutput](
        name="run.wait",
        handler=run_wait,
        sync_handler=run_wait_sync,
        input_type=RunWaitInput,
        output_type=RunDetailOutput,
        cli_group="run",
        cli_name="wait",
        mcp_name="run_wait",
        description="Wait until a run reaches terminal status.",
    )
)
