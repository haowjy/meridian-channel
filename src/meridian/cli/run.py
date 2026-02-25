"""CLI command handlers for run.* operations."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Annotated, Any, cast

from cyclopts import App, Parameter

from meridian.lib.domain import RunStatus
from meridian.lib.ops.registry import get_all_operations
from meridian.lib.ops.run import (
    RunActionOutput,
    RunContinueInput,
    RunCreateInput,
    RunListInput,
    RunRetryInput,
    RunShowInput,
    RunWaitInput,
    run_continue_sync,
    run_create_sync,
    run_list_sync,
    run_retry_sync,
    run_show_sync,
    run_wait_sync,
)

Emitter = Callable[[Any], None]


def _run_create(
    emit: Any,
    prompt: Annotated[str, Parameter(name=["--prompt", "-p"])] = "",
    model: Annotated[str, Parameter(name=["--model", "-m"])] = "",
    skill_flags: Annotated[tuple[str, ...], Parameter(name=["--skills", "-s"])] = (),
    references: Annotated[tuple[str, ...], Parameter(name=["--file", "-f"])] = (),
    template_vars: Annotated[tuple[str, ...], Parameter(name="--var")] = (),
    agent: Annotated[str | None, Parameter(name="--agent")] = None,
    report_path: Annotated[str, Parameter(name="--report-path")] = "report.md",
    dry_run: Annotated[bool, Parameter(name="--dry-run")] = False,
    workspace: Annotated[str | None, Parameter(name="--workspace")] = None,
    timeout_secs: Annotated[float | None, Parameter(name="--timeout-secs")] = None,
    permission_tier: Annotated[str | None, Parameter(name="--permission")] = None,
    unsafe: Annotated[bool, Parameter(name="--unsafe")] = False,
    budget_per_run_usd: Annotated[float | None, Parameter(name="--budget-per-run-usd")] = None,
    budget_per_workspace_usd: Annotated[
        float | None, Parameter(name="--budget-per-workspace-usd")
    ] = None,
    budget_usd: Annotated[float | None, Parameter(name="--budget-usd")] = None,
    guardrails: Annotated[tuple[str, ...], Parameter(name="--guardrail")] = (),
    secrets: Annotated[tuple[str, ...], Parameter(name="--secret")] = (),
) -> None:
    resolved_budget_per_run = budget_per_run_usd
    if resolved_budget_per_run is None:
        resolved_budget_per_run = budget_usd
    try:
        result = run_create_sync(
            RunCreateInput(
                prompt=prompt,
                model=model,
                skills=skill_flags,
                files=references,
                template_vars=template_vars,
                agent=agent,
                report_path=report_path,
                dry_run=dry_run,
                workspace=workspace,
                timeout_secs=timeout_secs,
                permission_tier=permission_tier,
                unsafe=unsafe,
                budget_per_run_usd=resolved_budget_per_run,
                budget_per_workspace_usd=budget_per_workspace_usd,
                guardrails=guardrails,
                secrets=secrets,
            )
        )
    except KeyError as exc:
        message = str(exc.args[0]) if exc.args else "Unknown skills."
        result = RunActionOutput(
            command="run.create",
            status="failed",
            error="unknown_skills",
            message=message,
        )
    emit(result)


def _run_list(
    emit: Any,
    workspace: Annotated[str | None, Parameter(name="--workspace")] = None,
    status: Annotated[str | None, Parameter(name="--status")] = None,
    model: Annotated[str | None, Parameter(name="--model")] = None,
    limit: Annotated[int, Parameter(name="--limit")] = 20,
    no_workspace: Annotated[bool, Parameter(name="--no-workspace")] = False,
    failed: Annotated[bool, Parameter(name="--failed")] = False,
) -> None:
    normalized_status: RunStatus | None = None
    if status is not None and status.strip():
        candidate = status.strip()
        if candidate not in {"queued", "running", "succeeded", "failed", "cancelled"}:
            raise ValueError(f"Unsupported run status '{status}'")
        normalized_status = cast("RunStatus", candidate)

    result = run_list_sync(
        RunListInput(
            workspace=workspace,
            status=normalized_status,
            model=model,
            limit=limit,
            no_workspace=no_workspace,
            failed=failed,
        )
    )
    emit(result)


def _run_show(
    emit: Any,
    run_id: str,
    include_report: Annotated[bool, Parameter(name="--include-report")] = False,
    include_files: Annotated[bool, Parameter(name="--include-files")] = False,
) -> None:
    emit(
        run_show_sync(
            RunShowInput(
                run_id=run_id,
                include_report=include_report,
                include_files=include_files,
            )
        )
    )


def _run_continue(
    emit: Any,
    run_id: str,
    prompt: Annotated[str, Parameter(name=["--prompt", "-p"])],
    model: Annotated[str, Parameter(name=["--model", "-m"])] = "",
    timeout_secs: Annotated[float | None, Parameter(name="--timeout-secs")] = None,
) -> None:
    emit(
        run_continue_sync(
            RunContinueInput(
                run_id=run_id,
                prompt=prompt,
                model=model,
                timeout_secs=timeout_secs,
            )
        )
    )


def _run_retry(
    emit: Any,
    run_id: str,
    prompt: Annotated[str | None, Parameter(name=["--prompt", "-p"])] = None,
    model: Annotated[str, Parameter(name=["--model", "-m"])] = "",
    timeout_secs: Annotated[float | None, Parameter(name="--timeout-secs")] = None,
) -> None:
    emit(
        run_retry_sync(
            RunRetryInput(
                run_id=run_id,
                prompt=prompt,
                model=model,
                timeout_secs=timeout_secs,
            )
        )
    )


def _run_wait(
    emit: Any,
    run_id: str,
    timeout_secs: Annotated[float, Parameter(name="--timeout-secs")] = 600.0,
    include_report: Annotated[bool, Parameter(name="--include-report")] = False,
    include_files: Annotated[bool, Parameter(name="--include-files")] = False,
) -> None:
    emit(
        run_wait_sync(
            RunWaitInput(
                run_id=run_id,
                timeout_secs=timeout_secs,
                include_report=include_report,
                include_files=include_files,
            )
        )
    )


def register_run_commands(app: App, emit: Emitter) -> tuple[set[str], dict[str, str]]:
    """Register run CLI commands using registry metadata as source of truth."""

    handlers: dict[str, Callable[[], Callable[..., None]]] = {
        "run.create": lambda: partial(_run_create, emit),
        "run.list": lambda: partial(_run_list, emit),
        "run.show": lambda: partial(_run_show, emit),
        "run.continue": lambda: partial(_run_continue, emit),
        "run.retry": lambda: partial(_run_retry, emit),
        "run.wait": lambda: partial(_run_wait, emit),
    }

    registered: set[str] = set()
    descriptions: dict[str, str] = {}

    for op in get_all_operations():
        if op.cli_group != "run" or op.mcp_only:
            continue
        handler_factory = handlers.get(op.name)
        if handler_factory is None:
            raise ValueError(f"No CLI handler registered for operation '{op.name}'")
        handler = handler_factory()
        handler.__name__ = f"cmd_{op.cli_group}_{op.cli_name}"
        app.command(handler, name=op.cli_name, help=op.description)
        registered.add(f"{op.cli_group}.{op.cli_name}")
        descriptions[op.name] = op.description

    app.default(partial(_run_create, emit))
    return registered, descriptions
