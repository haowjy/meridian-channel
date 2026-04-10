"""Resolved launch spec models for harness adapters."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from meridian.lib.harness.adapter import PermissionResolver, SpawnParams
from meridian.lib.safety.permissions import PermissionConfig


class ResolvedLaunchSpec(BaseModel):
    """Transport-neutral resolved configuration for one harness launch."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    model: str | None = None
    effort: str | None = None
    prompt: str = ""
    continue_session_id: str | None = None
    continue_fork: bool = False
    permission_config: PermissionConfig = Field(default_factory=PermissionConfig)
    permission_resolver: PermissionResolver | None = None
    extra_args: tuple[str, ...] = ()
    report_output_path: str | None = None
    interactive: bool = False


class ClaudeLaunchSpec(ResolvedLaunchSpec):
    """Claude-specific resolved launch spec."""

    appended_system_prompt: str | None = None
    agents_payload: str | None = None
    agent_name: str | None = None


class CodexLaunchSpec(ResolvedLaunchSpec):
    """Codex-specific resolved launch spec."""

    approval_mode: str = "default"
    sandbox_mode: str | None = None


class OpenCodeLaunchSpec(ResolvedLaunchSpec):
    """OpenCode-specific resolved launch spec."""

    agent_name: str | None = None
    skills: tuple[str, ...] = ()


def resolve_permission_config(perms: PermissionResolver) -> PermissionConfig:
    """Return resolver config when available, otherwise default permissions."""

    config = getattr(perms, "config", None)
    if isinstance(config, PermissionConfig):
        return config
    fallback_config = getattr(perms, "fallback_config", None)
    if isinstance(fallback_config, PermissionConfig):
        return fallback_config
    allowlist = getattr(perms, "allowlist", None)
    allowlist_fallback = getattr(allowlist, "fallback_config", None)
    if isinstance(allowlist_fallback, PermissionConfig):
        return allowlist_fallback
    denylist = getattr(perms, "denylist", None)
    denylist_fallback = getattr(denylist, "fallback_config", None)
    if isinstance(denylist_fallback, PermissionConfig):
        return denylist_fallback
    return PermissionConfig()


_SPEC_HANDLED_FIELDS: frozenset[str] = frozenset(
    {
        "prompt",
        "model",
        "effort",
        "skills",
        "agent",
        "adhoc_agent_payload",
        "extra_args",
        "repo_root",
        "mcp_tools",  # handled in env.py, not carried in the launch spec
        "interactive",
        "continue_harness_session_id",
        "continue_fork",
        "appended_system_prompt",
        "report_output_path",
    }
)

assert set(SpawnParams.model_fields) == _SPEC_HANDLED_FIELDS, (
    "SpawnParams fields changed. Update resolve_launch_spec() and _SPEC_HANDLED_FIELDS. "
    f"Missing: {set(SpawnParams.model_fields) - _SPEC_HANDLED_FIELDS}, "
    f"Extra: {_SPEC_HANDLED_FIELDS - set(SpawnParams.model_fields)}"
)
