"""Run operations used by CLI, MCP, and DirectAdapter surfaces."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import structlog

from meridian.lib.config import load_agent_profile, load_model_guidance
from meridian.lib.config.agent import AgentProfile
from meridian.lib.domain import RunCreateParams, RunStatus
from meridian.lib.exec.spawn import execute_with_finalization
from meridian.lib.exec.terminal import TerminalEventFilter, resolve_visible_categories
from meridian.lib.ops._runtime import (
    OperationRuntime,
    build_runtime,
    build_runtime_from_root_and_config,
    resolve_runtime_root_and_config,
    resolve_workspace_id,
)
from meridian.lib.ops.registry import OperationSpec, operation
from meridian.lib.prompt import (
    compose_run_prompt_text,
    load_reference_files,
    load_skill_contents,
    parse_template_assignments,
    resolve_run_defaults,
)
from meridian.lib.safety.budget import Budget, normalize_budget
from meridian.lib.safety.guardrails import normalize_guardrail_paths
from meridian.lib.safety.permissions import (
    PermissionConfig,
    TieredPermissionResolver,
    build_permission_config,
    parse_permission_tier,
)
from meridian.lib.safety.redaction import SecretSpec, parse_secret_specs, secrets_env_overrides
from meridian.lib.types import ModelId, RunId

if TYPE_CHECKING:
    from meridian.lib.formatting import FormatContext

_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()
logger = structlog.get_logger(__name__)
_LEGACY_DEFAULT_AGENT_SKILLS: tuple[str, ...] = ("run-agent", "agent")
_TIER_RANKS = {
    "read-only": 0,
    "workspace-write": 1,
    "full-access": 2,
    "danger": 3,
}


def _empty_template_vars() -> dict[str, str]:
    return {}


@dataclass(frozen=True, slots=True)
class RunCreateInput:
    prompt: str = ""
    model: str = ""
    skills: tuple[str, ...] = ()
    files: tuple[str, ...] = ()
    template_vars: tuple[str, ...] = ()
    agent: str | None = None
    report_path: str = "report.md"
    dry_run: bool = False
    verbose: bool = False
    quiet: bool = False
    stream: bool = False
    workspace: str | None = None
    repo_root: str | None = None
    timeout_secs: float | None = None
    permission_tier: str | None = None
    unsafe: bool = False
    budget_per_run_usd: float | None = None
    budget_per_workspace_usd: float | None = None
    guardrails: tuple[str, ...] = ()
    secrets: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RunActionOutput:
    command: str
    status: str
    run_id: str | None = None
    message: str | None = None
    error: str | None = None
    current_depth: int | None = None
    max_depth: int | None = None
    model: str | None = None
    harness_id: str | None = None
    warning: str | None = None
    agent: str | None = None
    skills: tuple[str, ...] = ()
    reference_files: tuple[str, ...] = ()
    template_vars: dict[str, str] = field(default_factory=_empty_template_vars)
    report_path: str | None = None
    composed_prompt: str | None = None
    cli_command: tuple[str, ...] = ()
    exit_code: int | None = None
    duration_secs: float | None = None

    def format_text(self, ctx: FormatContext | None = None) -> str:
        """Compact single-line summary for text output mode."""
        parts: list[str] = [self.command, self.status]
        if self.run_id is not None:
            parts.append(self.run_id)
        if self.model is not None:
            parts.append(f"model={self.model}")
        if self.harness_id is not None:
            parts.append(f"harness={self.harness_id}")
        if self.skills:
            parts.append(f"skills={','.join(self.skills)}")
        if self.duration_secs is not None:
            parts.append(f"{self.duration_secs:.1f}s")
        if self.exit_code is not None:
            parts.append(f"exit={self.exit_code}")
        if self.message is not None:
            parts.append(self.message)
        if self.error is not None:
            parts.append(f"error={self.error}")
        if self.warning is not None:
            parts.append(f"warning={self.warning}")
        return "  ".join(parts)


@dataclass(frozen=True, slots=True)
class RunListInput:
    workspace: str | None = None
    status: RunStatus | None = None
    model: str | None = None
    limit: int = 20
    no_workspace: bool = False
    failed: bool = False
    repo_root: str | None = None


@dataclass(frozen=True, slots=True)
class RunListEntry:
    run_id: str
    status: str
    model: str
    workspace_id: str | None
    duration_secs: float | None
    cost_usd: float | None

    def as_row(self) -> list[str]:
        """Return columnar cells for tabular alignment."""
        return [
            self.run_id,
            self.status,
            self.model,
            self.workspace_id if self.workspace_id is not None else "-",
            f"{self.duration_secs:.1f}s" if self.duration_secs is not None else "-",
            f"${self.cost_usd:.2f}" if self.cost_usd is not None else "-",
        ]


@dataclass(frozen=True, slots=True)
class RunListOutput:
    runs: tuple[RunListEntry, ...]

    def format_text(self, ctx: FormatContext | None = None) -> str:
        """Columnar list of runs for text output mode."""
        if not self.runs:
            return "(no runs)"
        from meridian.cli.format_helpers import tabular

        return tabular([entry.as_row() for entry in self.runs])


@dataclass(frozen=True, slots=True)
class RunShowInput:
    run_id: str
    include_report: bool = False
    include_files: bool = False
    repo_root: str | None = None


@dataclass(frozen=True, slots=True)
class RunDetailOutput:
    run_id: str
    status: str
    model: str
    harness: str
    workspace_id: str | None
    started_at: str
    finished_at: str | None
    duration_secs: float | None
    exit_code: int | None
    failure_reason: str | None
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    report_path: str | None
    report_summary: str | None
    report: str | None
    files_touched: tuple[str, ...] | None
    skills: tuple[str, ...]

    def format_text(self, ctx: FormatContext | None = None) -> str:
        """Key-value detail view for text output mode. Omits None/empty fields."""
        from meridian.cli.format_helpers import kv_block

        status_str = self.status
        if self.exit_code is not None:
            status_str += f" (exit {self.exit_code})"

        pairs: list[tuple[str, str | None]] = [
            ("Run", self.run_id),
            ("Status", status_str),
            ("Model", f"{self.model} ({self.harness})"),
            ("Duration", f"{self.duration_secs:.1f}s" if self.duration_secs is not None else None),
            ("Workspace", self.workspace_id),
            ("Skills", ", ".join(self.skills) if self.skills else None),
            ("Failure", self.failure_reason),
            ("Cost", f"${self.cost_usd:.4f}" if self.cost_usd is not None else None),
            ("Report", self.report_path),
        ]
        return kv_block(pairs)


@dataclass(frozen=True, slots=True)
class RunContinueInput:
    run_id: str
    prompt: str
    model: str = ""
    timeout_secs: float | None = None
    repo_root: str | None = None


@dataclass(frozen=True, slots=True)
class RunRetryInput:
    run_id: str
    prompt: str | None = None
    model: str = ""
    timeout_secs: float | None = None
    repo_root: str | None = None


@dataclass(frozen=True, slots=True)
class RunWaitInput:
    run_id: str
    timeout_secs: float | None = None
    poll_interval_secs: float | None = None
    include_report: bool = False
    include_files: bool = False
    repo_root: str | None = None


@dataclass(frozen=True, slots=True)
class _PreparedCreate:
    model: str
    harness_id: str
    warning: str | None
    composed_prompt: str
    skills: tuple[str, ...]
    reference_files: tuple[str, ...]
    template_vars: dict[str, str]
    report_path: str
    agent_name: str | None
    cli_command: tuple[str, ...]
    permission_config: PermissionConfig
    budget: Budget | None
    guardrails: tuple[str, ...]
    secrets: tuple[SecretSpec, ...]


@dataclass(frozen=True, slots=True)
class RunListFilters:
    """Type-safe run-list filters converted into parameterized SQL."""

    model: str | None = None
    workspace: str | None = None
    no_workspace: bool = False
    status: RunStatus | None = None
    failed: bool = False
    limit: int = 20


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


def _normalize_skill_flags(skill_flags: tuple[str, ...]) -> tuple[str, ...]:
    parsed: list[str] = []
    for flag in skill_flags:
        for candidate in flag.split(","):
            normalized = candidate.strip()
            if normalized:
                parsed.append(normalized)
    return tuple(parsed)


def _load_model_guidance_text() -> str:
    try:
        return load_model_guidance().content
    except FileNotFoundError:
        return ""


def _merge_warnings(primary: str | None, secondary: str | None) -> str | None:
    if primary and secondary:
        return f"{primary}; {secondary}"
    return primary or secondary


def _permission_tier_from_profile(agent_sandbox: str | None) -> str | None:
    if agent_sandbox is None:
        return None
    normalized = agent_sandbox.strip().lower()
    if not normalized:
        return None
    mapping = {
        "read-only": "read-only",
        "workspace-write": "workspace-write",
        "danger-full-access": "full-access",
        "unrestricted": "full-access",
    }
    return mapping.get(normalized)


def _warn_profile_tier_escalation(
    *,
    profile: AgentProfile | None,
    inferred_tier: str | None,
    default_tier: str,
) -> None:
    if profile is None or inferred_tier is None:
        return
    try:
        resolved_inferred = parse_permission_tier(inferred_tier)
        resolved_default = parse_permission_tier(default_tier)
    except ValueError:
        return
    if _TIER_RANKS[resolved_inferred.value] <= _TIER_RANKS[resolved_default.value]:
        return
    logger.warning(
        f"Agent profile '{profile.name}' infers {resolved_inferred.value} "
        f"(config default: {resolved_default.value}). Use --permission to override."
    )


def _build_create_payload(
    payload: RunCreateInput,
    *,
    runtime: OperationRuntime | None = None,
) -> _PreparedCreate:
    runtime_bundle = runtime or build_runtime(payload.repo_root)
    explicit_requested_skills = _normalize_skill_flags(payload.skills)
    requested_skills = explicit_requested_skills
    profile: AgentProfile | None = None
    if payload.agent:
        profile = load_agent_profile(
            payload.agent,
            repo_root=runtime_bundle.repo_root,
            search_paths=runtime_bundle.config.search_paths,
        )
    else:
        configured_default_agent = runtime_bundle.config.default_agent.strip()
        if configured_default_agent:
            try:
                profile = load_agent_profile(
                    configured_default_agent,
                    repo_root=runtime_bundle.repo_root,
                    search_paths=runtime_bundle.config.search_paths,
                )
            except FileNotFoundError:
                requested_skills = (*_LEGACY_DEFAULT_AGENT_SKILLS, *requested_skills)
        else:
            requested_skills = (*_LEGACY_DEFAULT_AGENT_SKILLS, *requested_skills)

    defaults = resolve_run_defaults(
        payload.model,
        requested_skills,
        profile=profile,
    )

    from meridian.lib.config.skill_registry import SkillRegistry

    registry = SkillRegistry(
        repo_root=runtime_bundle.repo_root,
        search_paths=runtime_bundle.config.search_paths,
    )
    if not registry.list():
        registry.reindex()

    available_skill_names = {item.name for item in registry.list()}
    missing_skills = tuple(
        skill_name for skill_name in defaults.skills if skill_name not in available_skill_names
    )
    explicit_skills = set(explicit_requested_skills)
    unknown_explicit = tuple(
        skill_name for skill_name in missing_skills if skill_name in explicit_skills
    )
    if unknown_explicit:
        raise KeyError(f"Unknown skills: {', '.join(unknown_explicit)}")

    # Implicit/default skills may be unavailable in lightweight repositories used by tests.
    # We skip only those missing implicit skills to keep dry-run and MCP surfaces usable.
    resolved_skill_names = tuple(
        skill_name for skill_name in defaults.skills if skill_name in available_skill_names
    )
    loaded_skills = load_skill_contents(registry, resolved_skill_names)
    loaded_references = load_reference_files(payload.files)
    parsed_template_vars = parse_template_assignments(payload.template_vars)

    composed_prompt = compose_run_prompt_text(
        skills=loaded_skills,
        references=loaded_references,
        user_prompt=payload.prompt,
        report_path=payload.report_path,
        agent_body=defaults.agent_body,
        model_guidance=_load_model_guidance_text(),
        template_variables=parsed_template_vars,
    )

    harness, route_warning = runtime_bundle.harness_registry.route(defaults.model)
    missing_skills_warning = (
        f"Skipped unavailable implicit skills: {', '.join(missing_skills)}."
        if missing_skills
        else None
    )
    warning = _merge_warnings(route_warning, missing_skills_warning)
    from meridian.lib.harness.adapter import RunParams

    inferred_tier = _permission_tier_from_profile(profile.sandbox if profile is not None else None)
    if payload.permission_tier is None:
        _warn_profile_tier_escalation(
            profile=profile,
            inferred_tier=inferred_tier,
            default_tier=runtime_bundle.config.default_permission_tier,
        )
    permission_config = build_permission_config(
        payload.permission_tier or inferred_tier,
        unsafe=payload.unsafe,
        default_tier=runtime_bundle.config.default_permission_tier,
    )
    budget = normalize_budget(
        per_run_usd=payload.budget_per_run_usd,
        per_workspace_usd=payload.budget_per_workspace_usd,
    )
    guardrails = normalize_guardrail_paths(payload.guardrails, repo_root=runtime_bundle.repo_root)
    secrets = parse_secret_specs(payload.secrets)

    preview_command = tuple(
        harness.build_command(
            RunParams(
                prompt=composed_prompt,
                model=ModelId(defaults.model),
                skills=tuple(skill.name for skill in loaded_skills),
                agent=defaults.agent_name,
            ),
            TieredPermissionResolver(permission_config),
        )
    )

    return _PreparedCreate(
        model=defaults.model,
        harness_id=str(harness.id),
        warning=warning,
        composed_prompt=composed_prompt,
        skills=tuple(skill.name for skill in loaded_skills),
        reference_files=tuple(str(reference.path) for reference in loaded_references),
        template_vars=parsed_template_vars,
        report_path=Path(payload.report_path).expanduser().resolve().as_posix(),
        agent_name=defaults.agent_name,
        cli_command=preview_command,
        permission_config=permission_config,
        budget=budget,
        guardrails=tuple(path.as_posix() for path in guardrails),
        secrets=secrets,
    )


def _read_run_row(repo_root: Path, run_id: str) -> sqlite3.Row | None:
    db_path = repo_root / ".meridian" / "index" / "runs.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            """
            SELECT
                id,
                workspace_id,
                prompt,
                model,
                harness,
                status,
                started_at,
                finished_at,
                duration_secs,
                exit_code,
                failure_reason,
                input_tokens,
                output_tokens,
                total_cost_usd,
                report_path,
                skills,
                files_touched_count
            FROM runs
            WHERE id = ?
            """,
            (run_id,),
        ).fetchone()
    finally:
        conn.close()


def _read_report_text(repo_root: Path, report_path: str | None) -> str | None:
    if report_path is None:
        return None
    path = Path(report_path)
    resolved = path if path.is_absolute() else repo_root / path
    if not resolved.exists() or not resolved.is_file():
        return None
    return resolved.read_text(encoding="utf-8", errors="ignore").strip() or None


def _read_files_touched(repo_root: Path, run_id: str) -> tuple[str, ...]:
    from meridian.lib.extract.files_touched import extract_files_touched
    from meridian.lib.state.artifact_store import LocalStore

    artifacts = LocalStore(repo_root / ".meridian" / "artifacts")
    return extract_files_touched(artifacts, RunId(run_id))


def _detail_from_row(
    *,
    repo_root: Path,
    row: sqlite3.Row,
    include_report: bool,
    include_files: bool,
) -> RunDetailOutput:
    report_path = cast("str | None", row["report_path"])
    report_text = _read_report_text(repo_root, report_path)
    report_summary = report_text[:500] if report_text else None

    files_touched: tuple[str, ...] | None = None
    if include_files:
        files_touched = _read_files_touched(repo_root, str(row["id"]))

    skills_text = str(row["skills"] or "[]")
    parsed_skills_payload: object
    try:
        parsed_skills_payload = json.loads(skills_text)
    except json.JSONDecodeError:
        parsed_skills_payload = []
    parsed_skills = cast(
        "list[object]",
        parsed_skills_payload if isinstance(parsed_skills_payload, list) else [],
    )
    skills = tuple(str(item) for item in parsed_skills if isinstance(item, str))

    return RunDetailOutput(
        run_id=str(row["id"]),
        status=str(row["status"]),
        model=str(row["model"]),
        harness=str(row["harness"]),
        workspace_id=cast("str | None", row["workspace_id"]),
        started_at=str(row["started_at"]),
        finished_at=cast("str | None", row["finished_at"]),
        duration_secs=cast("float | None", row["duration_secs"]),
        exit_code=cast("int | None", row["exit_code"]),
        failure_reason=cast("str | None", row["failure_reason"]),
        input_tokens=cast("int | None", row["input_tokens"]),
        output_tokens=cast("int | None", row["output_tokens"]),
        cost_usd=cast("float | None", row["total_cost_usd"]),
        report_path=report_path,
        report_summary=report_summary,
        report=report_text if include_report else None,
        files_touched=files_touched,
        skills=skills,
    )


def _run_child_env(
    workspace_id: str | None,
    secrets: tuple[SecretSpec, ...],
    parent_run_id: str | None = None,
) -> dict[str, str]:
    child_env = os.environ.copy()
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

    db_path = repo_root / ".meridian" / "index" / "runs.db"
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
    prepared: _PreparedCreate,
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
            cwd=runtime.repo_root,
            timeout_seconds=payload.timeout_secs,
            kill_grace_seconds=runtime.config.kill_grace_seconds,
            skills=prepared.skills,
            agent=prepared.agent_name,
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
        cwd=runtime.repo_root,
        timeout_seconds=timeout_secs,
        kill_grace_seconds=runtime.config.kill_grace_seconds,
        skills=skills,
        agent=agent_name,
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


def run_create_sync(payload: RunCreateInput) -> RunActionOutput:
    runtime: OperationRuntime
    if not payload.dry_run:
        resolved_root, config = resolve_runtime_root_and_config(payload.repo_root)
        current_depth, max_depth = _depth_limits(config.max_depth)
        if current_depth >= max_depth:
            return _depth_exceeded_output(current_depth, max_depth)
        runtime = build_runtime_from_root_and_config(resolved_root, config)
    else:
        runtime = build_runtime(payload.repo_root)

    prepared = _build_create_payload(payload, runtime=runtime)
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

    return _execute_run_blocking(payload=payload, prepared=prepared, runtime=runtime)


async def run_create(payload: RunCreateInput) -> RunActionOutput:
    runtime: OperationRuntime
    if not payload.dry_run:
        resolved_root, config = resolve_runtime_root_and_config(payload.repo_root)
        current_depth, max_depth = _depth_limits(config.max_depth)
        if current_depth >= max_depth:
            return _depth_exceeded_output(current_depth, max_depth)
        runtime = build_runtime_from_root_and_config(resolved_root, config)
    else:
        runtime = build_runtime(payload.repo_root)

    prepared = _build_create_payload(payload, runtime=runtime)
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

    workspace_id = resolve_workspace_id(payload.workspace)
    run = await runtime.run_store.create(
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

    task = asyncio.create_task(
        _execute_run_non_blocking(
            run_id=run.run_id,
            repo_root=runtime.repo_root,
            timeout_secs=payload.timeout_secs,
            skills=prepared.skills,
            agent_name=prepared.agent_name,
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
    runtime = build_runtime(payload.repo_root)
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

    conn = sqlite3.connect(runtime.state.paths.db_path)
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


def _build_run_list_query(filters: RunListFilters) -> tuple[str, tuple[object, ...]]:
    where: list[str] = []
    params: list[object] = []

    if filters.workspace is not None:
        where.append("workspace_id = ?")
        params.append(filters.workspace)
    if filters.no_workspace:
        where.append("workspace_id IS NULL")
    if filters.status is not None:
        where.append("status = ?")
        params.append(filters.status)
    if filters.failed:
        where.append("status = ?")
        params.append("failed")
    if filters.model is not None:
        where.append("model = ?")
        params.append(filters.model)

    query = "SELECT id, status, model, workspace_id, duration_secs, total_cost_usd FROM runs"
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY started_at DESC LIMIT ?"
    params.append(filters.limit if filters.limit > 0 else 20)
    return query, tuple(params)


async def run_list(payload: RunListInput) -> RunListOutput:
    return await asyncio.to_thread(run_list_sync, payload)


def run_show_sync(payload: RunShowInput) -> RunDetailOutput:
    runtime = build_runtime(payload.repo_root)
    row = _read_run_row(runtime.repo_root, payload.run_id)
    if row is None:
        raise ValueError(f"Run '{payload.run_id}' not found")
    return _detail_from_row(
        repo_root=runtime.repo_root,
        row=row,
        include_report=payload.include_report,
        include_files=payload.include_files,
    )


async def run_show(payload: RunShowInput) -> RunDetailOutput:
    return await asyncio.to_thread(run_show_sync, payload)


def _run_is_terminal(status: str) -> bool:
    return status not in {"queued", "running"}


def run_wait_sync(payload: RunWaitInput) -> RunDetailOutput:
    runtime = build_runtime(payload.repo_root)
    timeout_secs = (
        payload.timeout_secs
        if payload.timeout_secs is not None
        else runtime.config.wait_timeout_seconds
    )
    deadline = time.monotonic() + max(timeout_secs, 0.0)
    poll = (
        payload.poll_interval_secs
        if payload.poll_interval_secs is not None
        # run.wait polling is a read-side retry loop, so we intentionally reuse
        # retry_backoff_seconds as the default cadence when no poll interval is set.
        else runtime.config.retry_backoff_seconds
    )
    if poll <= 0:
        poll = runtime.config.retry_backoff_seconds

    while True:
        row = _read_run_row(runtime.repo_root, payload.run_id)
        if row is None:
            raise ValueError(f"Run '{payload.run_id}' not found")

        status = str(row["status"])
        if _run_is_terminal(status):
            return _detail_from_row(
                repo_root=runtime.repo_root,
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
    runtime = build_runtime(payload.repo_root)
    derived_prompt = _prompt_for_follow_up(payload.run_id, runtime.repo_root, payload.prompt)
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
    runtime = build_runtime(payload.repo_root)
    derived_prompt = _prompt_for_follow_up(payload.run_id, runtime.repo_root, payload.prompt)
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
