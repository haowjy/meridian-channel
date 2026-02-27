"""Run create-input validation and payload preparation helpers."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from meridian.lib.config import load_agent_profile, load_model_guidance
from meridian.lib.config.agent import AgentProfile
from meridian.lib.config.catalog import resolve_model
from meridian.lib.config.routing import route_model
from meridian.lib.harness.registry import get_default_harness_registry
from meridian.lib.ops._runtime import OperationRuntime, build_runtime, resolve_runtime_root_and_config
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
    _permission_tier_from_profile,
    _warn_profile_tier_escalation,
    PermissionConfig,
    TieredPermissionResolver,
    build_permission_config,
    validate_permission_config_for_harness,
)
from meridian.lib.safety.redaction import SecretSpec, parse_secret_specs
from meridian.lib.types import ModelId

from ._run_models import RunCreateInput

if TYPE_CHECKING:
    from meridian.lib.config.settings import MeridianConfig
    from meridian.lib.harness.registry import HarnessRegistry

logger = structlog.get_logger(__name__)
_LEGACY_DEFAULT_AGENT_SKILLS: tuple[str, ...] = ("run-agent", "agent")


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
    mcp_tools: tuple[str, ...]
    agent_name: str | None
    cli_command: tuple[str, ...]
    permission_config: PermissionConfig
    budget: Budget | None
    guardrails: tuple[str, ...]
    secrets: tuple[SecretSpec, ...]


@dataclass(frozen=True, slots=True)
class _CreateRuntimeView:
    """Subset of runtime dependencies needed for payload composition."""

    repo_root: Path
    config: MeridianConfig
    harness_registry: HarnessRegistry


def _normalize_skill_flags(skill_flags: tuple[str, ...]) -> tuple[str, ...]:
    parsed: list[str] = []
    for flag in skill_flags:
        for candidate in flag.split(","):
            normalized = candidate.strip()
            if normalized:
                parsed.append(normalized)
    return tuple(parsed)


def _looks_like_alias_identifier(candidate: str) -> bool:
    return "/" not in candidate and "-" not in candidate and "." not in candidate


def _validate_requested_model(
    requested_model: str,
    *,
    repo_root: str | None,
) -> tuple[str, str | None]:
    normalized = requested_model.strip()
    if not normalized:
        return "", None

    explicit_root = Path(repo_root).expanduser().resolve() if repo_root else None
    try:
        return str(resolve_model(normalized, repo_root=explicit_root).model_id), None
    except KeyError:
        pass

    if _looks_like_alias_identifier(normalized):
        raise ValueError(
            f"Unknown model alias '{normalized}'. Run `meridian models list` to inspect aliases."
        )

    routed = route_model(normalized)
    if routed.warning is None:
        return normalized, f"Model '{normalized}' is not in catalog. Routing to '{routed.harness_id}'."

    raise ValueError(
        f"Unknown model '{normalized}'. Run `meridian models list` to inspect supported models."
    )


def _validate_create_input(payload: RunCreateInput) -> tuple[RunCreateInput, str | None]:
    if not payload.prompt.strip():
        raise ValueError("prompt required: use --prompt/-p with non-empty text.")

    resolved_model, model_warning = _validate_requested_model(
        payload.model,
        repo_root=payload.repo_root,
    )
    if resolved_model and resolved_model != payload.model:
        return replace(payload, model=resolved_model), model_warning
    return payload, model_warning


def _load_model_guidance_text() -> str:
    try:
        return load_model_guidance().content
    except FileNotFoundError:
        return ""


def _merge_warnings(primary: str | None, secondary: str | None) -> str | None:
    if primary and secondary:
        return f"{primary}; {secondary}"
    return primary or secondary


def _build_create_payload(
    payload: RunCreateInput,
    *,
    runtime: OperationRuntime | None = None,
    preflight_warning: str | None = None,
) -> _PreparedCreate:
    runtime_view: _CreateRuntimeView
    if runtime is not None:
        runtime_view = _CreateRuntimeView(
            repo_root=runtime.repo_root,
            config=runtime.config,
            harness_registry=runtime.harness_registry,
        )
    elif payload.dry_run:
        repo_root, config = resolve_runtime_root_and_config(payload.repo_root)
        runtime_view = _CreateRuntimeView(
            repo_root=repo_root,
            config=config,
            harness_registry=get_default_harness_registry(),
        )
    else:
        runtime_bundle = build_runtime(payload.repo_root)
        runtime_view = _CreateRuntimeView(
            repo_root=runtime_bundle.repo_root,
            config=runtime_bundle.config,
            harness_registry=runtime_bundle.harness_registry,
        )

    explicit_requested_skills = _normalize_skill_flags(payload.skills)
    requested_skills = explicit_requested_skills
    profile: AgentProfile | None = None
    if payload.agent:
        profile = load_agent_profile(
            payload.agent,
            repo_root=runtime_view.repo_root,
            search_paths=runtime_view.config.search_paths,
        )
    else:
        configured_default_agent = runtime_view.config.default_agent.strip()
        if configured_default_agent:
            try:
                profile = load_agent_profile(
                    configured_default_agent,
                    repo_root=runtime_view.repo_root,
                    search_paths=runtime_view.config.search_paths,
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
        repo_root=runtime_view.repo_root,
        search_paths=runtime_view.config.search_paths,
        readonly=payload.dry_run,
    )
    manifests = registry.list()
    if not manifests and not registry.readonly:
        registry.reindex()
        manifests = registry.list()

    available_skill_names = {item.name for item in manifests}
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

    harness, route_warning = runtime_view.harness_registry.route(defaults.model)
    missing_skills_warning = (
        f"Skipped unavailable implicit skills: {', '.join(missing_skills)}."
        if missing_skills
        else None
    )
    warning = _merge_warnings(route_warning, missing_skills_warning)
    warning = _merge_warnings(preflight_warning, warning)
    from meridian.lib.harness.adapter import RunParams

    inferred_tier = _permission_tier_from_profile(profile.sandbox if profile is not None else None)
    if payload.permission_tier is None:
        _warn_profile_tier_escalation(
            profile=profile,
            inferred_tier=inferred_tier,
            default_tier=runtime_view.config.default_permission_tier,
            warning_logger=logger,
        )
    permission_config = build_permission_config(
        payload.permission_tier or inferred_tier,
        unsafe=payload.unsafe,
        default_tier=runtime_view.config.default_permission_tier,
    )
    warning = _merge_warnings(
        warning,
        validate_permission_config_for_harness(
            harness_id=harness.id,
            config=permission_config,
        ),
    )
    budget = normalize_budget(
        per_run_usd=payload.budget_per_run_usd,
        per_workspace_usd=payload.budget_per_workspace_usd,
    )
    guardrails = normalize_guardrail_paths(payload.guardrails, repo_root=runtime_view.repo_root)
    secrets = parse_secret_specs(payload.secrets)

    preview_command = tuple(
        harness.build_command(
            RunParams(
                prompt=composed_prompt,
                model=ModelId(defaults.model),
                skills=tuple(skill.name for skill in loaded_skills),
                agent=defaults.agent_name,
                repo_root=runtime_view.repo_root.as_posix(),
                mcp_tools=profile.mcp_tools if profile is not None else (),
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
        mcp_tools=profile.mcp_tools if profile is not None else (),
        agent_name=defaults.agent_name,
        cli_command=preview_command,
        permission_config=permission_config,
        budget=budget,
        guardrails=tuple(path.as_posix() for path in guardrails),
        secrets=secrets,
    )
