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
    _depth_exceeded_output,
    _depth_limits,
    _emit_subrun_event,
    _execute_run_background,
    _execute_run_blocking,
    _execute_run_non_blocking,
    _read_non_negative_int_env,
    _track_task,
    logger,
)
from ._run_models import (
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
    RunStatsInput,
    RunStatsOutput,
    RunWaitInput,
    RunWaitMultiOutput,
)
from ._run_prepare import (
    _build_create_payload,
    _validate_create_input,
)
from ._run_query import (
    _build_run_list_query,
    _detail_from_row,
    _read_run_row,
    resolve_run_reference,
    resolve_run_references,
)

_run_child_env = _run_execute_module._run_child_env


def run_create_sync(payload: RunCreateInput) -> RunActionOutput:
    _run_prepare_module.build_permission_config = build_permission_config
    _run_prepare_module.validate_permission_config_for_harness = (
        validate_permission_config_for_harness
    )
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
    if payload.background:
        return _execute_run_background(payload=payload, prepared=prepared, runtime=runtime)
    return _execute_run_blocking(payload=payload, prepared=prepared, runtime=runtime)


async def run_create(payload: RunCreateInput) -> RunActionOutput:
    _run_prepare_module.build_permission_config = build_permission_config
    _run_prepare_module.validate_permission_config_for_harness = (
        validate_permission_config_for_harness
    )
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
            continue_session_id=prepared.continue_session_id,
            continue_fork=prepared.continue_fork,
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


def _runs_table_columns(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("PRAGMA table_info(runs)").fetchall()
    return {
        str(row["name"])
        for row in rows
        if row["name"] is not None
    }


def _resolve_run_session_column(columns: set[str]) -> str | None:
    if "session_id" in columns:
        return "session_id"
    if "harness_session_id" in columns:
        return "harness_session_id"
    return None


def run_stats_sync(payload: RunStatsInput) -> RunStatsOutput:
    repo_root, _ = resolve_runtime_root_and_config(payload.repo_root)
    db_path = resolve_state_paths(repo_root).db_path
    if not db_path.is_file():
        return RunStatsOutput(
            total_runs=0,
            succeeded=0,
            failed=0,
            cancelled=0,
            running=0,
            total_duration_secs=0.0,
            total_cost_usd=0.0,
            models={},
        )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        columns = _runs_table_columns(conn)
        where: list[str] = []
        params: list[object] = []

        workspace = payload.workspace.strip() if payload.workspace is not None else ""
        if workspace:
            where.append("workspace_id = ?")
            params.append(workspace)

        session = payload.session.strip() if payload.session is not None else ""
        if session:
            session_column = _resolve_run_session_column(columns)
            if session_column is not None:
                where.append(f"{session_column} = ?")
                params.append(session)
            # TODO: support session filtering on legacy schemas that have no session column.

        where_clause = f" WHERE {' AND '.join(where)}" if where else ""

        aggregate_row = conn.execute(
            (
                "SELECT "
                "COUNT(*) AS total_runs, "
                "COALESCE(SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END), 0) AS succeeded, "
                "COALESCE(SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END), 0) AS failed, "
                "COALESCE(SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END), 0) AS cancelled, "
                "COALESCE(SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END), 0) AS running, "
                "COALESCE(SUM(COALESCE(duration_secs, 0.0)), 0.0) AS total_duration_secs, "
                "COALESCE(SUM(COALESCE(total_cost_usd, 0.0)), 0.0) AS total_cost_usd "
                f"FROM runs{where_clause}"
            ),
            tuple(params),
        ).fetchone()
        if aggregate_row is None:
            return RunStatsOutput(
                total_runs=0,
                succeeded=0,
                failed=0,
                cancelled=0,
                running=0,
                total_duration_secs=0.0,
                total_cost_usd=0.0,
                models={},
            )

        model_rows = conn.execute(
            (
                "SELECT model, COUNT(*) AS run_count "
                f"FROM runs{where_clause} "
                "GROUP BY model "
                "ORDER BY run_count DESC, model ASC"
            ),
            tuple(params),
        ).fetchall()
    finally:
        conn.close()

    return RunStatsOutput(
        total_runs=int(aggregate_row["total_runs"] or 0),
        succeeded=int(aggregate_row["succeeded"] or 0),
        failed=int(aggregate_row["failed"] or 0),
        cancelled=int(aggregate_row["cancelled"] or 0),
        running=int(aggregate_row["running"] or 0),
        total_duration_secs=float(aggregate_row["total_duration_secs"] or 0.0),
        total_cost_usd=float(aggregate_row["total_cost_usd"] or 0.0),
        models={
            str(row["model"]): int(row["run_count"])
            for row in model_rows
            if row["model"] is not None
        },
    )


async def run_stats(payload: RunStatsInput) -> RunStatsOutput:
    return await asyncio.to_thread(run_stats_sync, payload)


def run_show_sync(payload: RunShowInput) -> RunDetailOutput:
    repo_root, _ = resolve_runtime_root_and_config(payload.repo_root)
    run_id = resolve_run_reference(repo_root, payload.run_id)
    row = _read_run_row(repo_root, run_id)
    if row is None:
        raise ValueError(f"Run '{run_id}' not found")
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


def _normalize_wait_run_ids(payload: RunWaitInput) -> tuple[str, ...]:
    candidates: list[str] = []
    for run_id in payload.run_ids:
        normalized = run_id.strip()
        if normalized:
            candidates.append(normalized)

    if payload.run_id is not None and payload.run_id.strip():
        candidates.append(payload.run_id.strip())

    deduped = tuple(dict.fromkeys(candidates))
    if not deduped:
        raise ValueError("At least one run_id is required")
    return deduped


def _build_wait_multi_output(results: tuple[RunDetailOutput, ...]) -> RunWaitMultiOutput:
    total_runs = len(results)
    succeeded_runs = sum(1 for run in results if run.status == "succeeded")
    failed_runs = sum(1 for run in results if run.status == "failed")
    cancelled_runs = sum(1 for run in results if run.status == "cancelled")
    any_failed = any(run.status in {"failed", "cancelled"} for run in results)

    run_id: str | None = None
    status: str | None = None
    exit_code: int | None = None
    if total_runs == 1:
        run_id = results[0].run_id
        status = results[0].status
        exit_code = results[0].exit_code

    return RunWaitMultiOutput(
        runs=results,
        total_runs=total_runs,
        succeeded_runs=succeeded_runs,
        failed_runs=failed_runs,
        cancelled_runs=cancelled_runs,
        any_failed=any_failed,
        run_id=run_id,
        status=status,
        exit_code=exit_code,
    )


def run_wait_sync(payload: RunWaitInput) -> RunWaitMultiOutput:
    repo_root, config = resolve_runtime_root_and_config(payload.repo_root)
    run_ids = resolve_run_references(repo_root, _normalize_wait_run_ids(payload))
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

    completed_rows: dict[str, sqlite3.Row] = {}
    pending: set[str] = set(run_ids)

    while True:
        for run_id in tuple(pending):
            row = _read_run_row(repo_root, run_id)
            if row is None:
                raise ValueError(f"Run '{run_id}' not found")

            status = str(row["status"])
            if _run_is_terminal(status):
                completed_rows[run_id] = row
                pending.remove(run_id)

        if not pending:
            details = tuple(
                _detail_from_row(
                    repo_root=repo_root,
                    row=completed_rows[run_id],
                    include_report=payload.include_report,
                    include_files=payload.include_files,
                )
                for run_id in run_ids
            )
            return _build_wait_multi_output(details)

        if time.monotonic() >= deadline:
            timed_out = "', '".join(sorted(pending))
            raise TimeoutError(f"Timed out waiting for run(s) '{timed_out}'")
        time.sleep(poll)


async def run_wait(payload: RunWaitInput) -> RunWaitMultiOutput:
    return await asyncio.to_thread(run_wait_sync, payload)


def _source_run_for_follow_up(payload_run_id: str, repo_root: Path) -> tuple[str, sqlite3.Row]:
    resolved_run_id = resolve_run_reference(repo_root, payload_run_id)
    row = _read_run_row(repo_root, resolved_run_id)
    if row is None:
        raise ValueError(f"Run '{resolved_run_id}' not found")
    return resolved_run_id, row


def _prompt_for_follow_up(source_run: sqlite3.Row, payload_run_id: str, prompt: str | None) -> str:
    if prompt is not None and prompt.strip():
        return prompt

    existing_prompt = str(source_run["prompt"] or "").strip()
    if not existing_prompt:
        raise ValueError(f"Run '{payload_run_id}' has no stored prompt")
    return existing_prompt


def _model_for_follow_up(source_run: sqlite3.Row, override_model: str) -> str:
    if override_model.strip():
        return override_model
    return str(source_run["model"] or "").strip()


def _with_command(result: RunActionOutput, command: str) -> RunActionOutput:
    return replace(result, command=command)


def run_continue_sync(payload: RunContinueInput) -> RunActionOutput:
    repo_root, _ = resolve_runtime_root_and_config(payload.repo_root)
    resolved_run_id, source_run = _source_run_for_follow_up(payload.run_id, repo_root)
    derived_prompt = _prompt_for_follow_up(source_run, resolved_run_id, payload.prompt)
    source_harness = str(source_run["harness"] or "").strip() or None
    source_session_id = str(source_run["harness_session_id"] or "").strip() or None
    # Note: agent is not forwarded from the original run, so
    # agent_explicitly_requested will be False and permission-escalation
    # warnings won't fire.  This is acceptable for continue/retry since
    # the user already approved the original run's permissions.
    create_input = RunCreateInput(
        prompt=derived_prompt,
        model=_model_for_follow_up(source_run, payload.model),
        repo_root=payload.repo_root,
        timeout_secs=payload.timeout_secs,
        continue_session_id=source_session_id,
        continue_harness=source_harness,
        continue_fork=payload.fork,
    )
    result = run_create_sync(create_input)
    return _with_command(result, "run.continue")


async def run_continue(payload: RunContinueInput) -> RunActionOutput:
    return await asyncio.to_thread(run_continue_sync, payload)


def run_retry_sync(payload: RunRetryInput) -> RunActionOutput:
    repo_root, _ = resolve_runtime_root_and_config(payload.repo_root)
    resolved_run_id, source_run = _source_run_for_follow_up(payload.run_id, repo_root)
    derived_prompt = _prompt_for_follow_up(source_run, resolved_run_id, payload.prompt)
    source_harness = str(source_run["harness"] or "").strip() or None
    source_session_id = str(source_run["harness_session_id"] or "").strip() or None
    create_input = RunCreateInput(
        prompt=derived_prompt,
        model=_model_for_follow_up(source_run, payload.model),
        repo_root=payload.repo_root,
        timeout_secs=payload.timeout_secs,
        continue_session_id=source_session_id,
        continue_harness=source_harness,
        continue_fork=payload.fork,
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
    OperationSpec[RunStatsInput, RunStatsOutput](
        name="run.stats",
        handler=run_stats,
        sync_handler=run_stats_sync,
        input_type=RunStatsInput,
        output_type=RunStatsOutput,
        cli_group="run",
        cli_name="stats",
        mcp_name="run_stats",
        description="Show aggregate run statistics with optional filters.",
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
    OperationSpec[RunWaitInput, RunWaitMultiOutput](
        name="run.wait",
        handler=run_wait,
        sync_handler=run_wait_sync,
        input_type=RunWaitInput,
        output_type=RunWaitMultiOutput,
        cli_group="run",
        cli_name="wait",
        mcp_name="run_wait",
        description="Wait until a run reaches terminal status.",
    )
)
