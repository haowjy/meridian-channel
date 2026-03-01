"""Shared launch-time resolution helpers for agent profiles, skills, and permissions."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from meridian.lib.config.agent import AgentProfile, load_agent_profile
from meridian.lib.config.settings import SearchPathConfig
from meridian.lib.config.skill_registry import SkillRegistry
from meridian.lib.domain import SkillContent
from meridian.lib.prompt.assembly import load_skill_contents
from meridian.lib.safety.permissions import permission_tier_from_profile

logger = logging.getLogger(__name__)


class _WarningLogger(Protocol):
    def warning(self, message: str, *args: object) -> None: ...


def load_agent_profile_with_fallback(
    *,
    repo_root: Path,
    search_paths: SearchPathConfig | None = None,
    requested_agent: str | None = None,
    configured_default: str = "",
    fallback_name: str = "agent",
) -> AgentProfile | None:
    """Load agent profile with a standard fallback chain.

    Resolution order:
    1. requested_agent (explicit --agent flag) -> load or raise
    2. configured_default (from config) -> try load
    3. fallback_name -> try load
    4. None (no profile)
    """

    requested_profile = requested_agent.strip() if requested_agent is not None else ""
    if requested_profile:
        return load_agent_profile(
            requested_profile,
            repo_root=repo_root,
            search_paths=search_paths,
        )

    configured_profile = configured_default.strip()
    if configured_profile:
        try:
            return load_agent_profile(
                configured_profile,
                repo_root=repo_root,
                search_paths=search_paths,
            )
        except FileNotFoundError:
            pass

    normalized_fallback = fallback_name.strip()
    if normalized_fallback and normalized_fallback != configured_profile:
        try:
            return load_agent_profile(
                normalized_fallback,
                repo_root=repo_root,
                search_paths=search_paths,
            )
        except FileNotFoundError:
            pass
    return None


@dataclass(frozen=True, slots=True)
class ResolvedSkills:
    skill_names: tuple[str, ...]
    loaded_skills: tuple[SkillContent, ...]
    skill_sources: dict[str, Path]
    missing_skills: tuple[str, ...]


def resolve_skills_from_profile(
    *,
    profile_skills: tuple[str, ...],
    repo_root: Path,
    search_paths: SearchPathConfig | None = None,
    readonly: bool = False,
) -> ResolvedSkills:
    """Load and resolve skills declared in an agent profile."""

    registry = SkillRegistry(
        repo_root=repo_root,
        search_paths=search_paths,
        readonly=readonly,
    )
    manifests = registry.list()
    if not manifests and not registry.readonly:
        registry.reindex()
        manifests = registry.list()

    available_skill_names = {item.name for item in manifests}
    missing_skills = tuple(
        skill_name for skill_name in profile_skills if skill_name not in available_skill_names
    )
    resolved_skill_names = tuple(
        skill_name for skill_name in profile_skills if skill_name in available_skill_names
    )
    loaded_skills = load_skill_contents(registry, resolved_skill_names)
    skill_sources = {
        skill.name: Path(skill.path).expanduser().resolve().parent for skill in loaded_skills
    }
    return ResolvedSkills(
        skill_names=tuple(skill.name for skill in loaded_skills),
        loaded_skills=loaded_skills,
        skill_sources=skill_sources,
        missing_skills=missing_skills,
    )


def resolve_permission_tier_from_profile(
    *,
    profile: AgentProfile | None,
    default_tier: str,
    warning_logger: _WarningLogger | None = None,
) -> str:
    """Infer permission tier from agent profile sandbox field."""

    sandbox_value = profile.sandbox if profile is not None else None
    inferred_tier = permission_tier_from_profile(sandbox_value)
    if inferred_tier is not None:
        return inferred_tier

    if profile is not None and sandbox_value is not None and sandbox_value.strip():
        sink = warning_logger or logger
        sink.warning(
            "Agent profile '%s' has unsupported sandbox '%s'; "
            "falling back to default permission tier '%s'.",
            profile.name,
            sandbox_value.strip(),
            default_tier,
        )
    return default_tier
