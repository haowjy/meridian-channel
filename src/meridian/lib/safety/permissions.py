"""Permission tiers and harness-flag translation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

import structlog

from meridian.lib.types import HarnessId

if TYPE_CHECKING:
    from meridian.lib.config.agent import AgentProfile

logger = structlog.get_logger(__name__)


class _WarningLogger(Protocol):
    def warning(self, message: str) -> None: ...


class PermissionTier(StrEnum):
    """Safety tiers applied to harness command construction."""

    READ_ONLY = "read-only"
    SPACE_WRITE = "space-write"
    FULL_ACCESS = "full-access"
    DANGER = "danger"


_TIER_RANKS = {
    "read-only": 0,
    "space-write": 1,
    "full-access": 2,
    "danger": 3,
}
_OPENCODE_DANGER_FALLBACK_WARNING = (
    "OpenCode has no danger-bypass flag; DANGER falls back to FULL_ACCESS."
)


@dataclass(frozen=True, slots=True)
class PermissionConfig:
    """Resolved permission configuration for one run."""

    tier: PermissionTier = PermissionTier.READ_ONLY
    unsafe: bool = False


def parse_permission_tier(
    raw: str | PermissionTier | None,
    *,
    default_tier: str | PermissionTier = PermissionTier.READ_ONLY,
) -> PermissionTier:
    """Parse one permission tier string."""

    resolved_default = _parse_permission_tier_value(default_tier)
    if raw is None:
        return resolved_default
    if isinstance(raw, PermissionTier):
        return raw

    normalized = raw.strip().lower()
    if not normalized:
        return resolved_default
    return _parse_permission_tier_value(normalized)


def permission_tier_from_profile(agent_sandbox: str | None) -> str | None:
    if agent_sandbox is None:
        return None
    normalized = agent_sandbox.strip().lower()
    if not normalized:
        return None
    mapping = {
        "read-only": "read-only",
        "space-write": "space-write",
        "full-access": "full-access",
        "danger-full-access": "full-access",
        "unrestricted": "full-access",
    }
    return mapping.get(normalized)


def _parse_permission_tier_value(raw: str | PermissionTier) -> PermissionTier:
    if isinstance(raw, PermissionTier):
        return raw

    normalized = raw.strip().lower()
    if not normalized:
        raise ValueError("Unsupported permission tier ''.")
    for candidate in PermissionTier:
        if candidate.value == normalized:
            return candidate
    allowed = ", ".join(item.value for item in PermissionTier)
    raise ValueError(f"Unsupported permission tier '{raw}'. Expected: {allowed}.")


def warn_profile_tier_escalation(
    *,
    profile: AgentProfile | None,
    inferred_tier: str | None,
    default_tier: str,
    warning_logger: _WarningLogger | None = None,
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
    sink = warning_logger or logger
    sink.warning(
        f"Agent profile '{profile.name}' infers {resolved_inferred.value} "
        f"(config default: {resolved_default.value}). Use --permission to override."
    )


def build_permission_config(
    tier: str | PermissionTier | None,
    *,
    unsafe: bool,
    default_tier: str | PermissionTier = PermissionTier.READ_ONLY,
) -> PermissionConfig:
    """Build and validate a permission configuration."""

    resolved = PermissionConfig(
        tier=parse_permission_tier(tier, default_tier=default_tier),
        unsafe=unsafe,
    )
    if resolved.tier is PermissionTier.DANGER and not resolved.unsafe:
        raise ValueError(
            "Permission tier 'danger' requires explicit --unsafe confirmation."
        )
    return resolved


def validate_permission_config_for_harness(
    *,
    harness_id: HarnessId,
    config: PermissionConfig,
) -> str | None:
    """Validate one permission config against harness-specific capability limits."""

    if harness_id == HarnessId("opencode") and config.tier is PermissionTier.DANGER:
        logger.warning(
            _OPENCODE_DANGER_FALLBACK_WARNING,
            harness_id=str(harness_id),
            requested_tier=config.tier.value,
            effective_tier=PermissionTier.FULL_ACCESS.value,
        )
        return _OPENCODE_DANGER_FALLBACK_WARNING
    return None


def _claude_allowed_tools(tier: PermissionTier) -> tuple[str, ...]:
    read_only = (
        "Read",
        "Glob",
        "Grep",
        "Bash(git status)",
        "Bash(git log)",
        "Bash(git diff)",
    )
    space_write = (
        *read_only,
        "Edit",
        "Write",
        "Bash(git add)",
        "Bash(git commit)",
    )
    full_access = (
        *space_write,
        "WebFetch",
        "WebSearch",
        "Bash",
    )
    if tier is PermissionTier.READ_ONLY:
        return read_only
    if tier is PermissionTier.SPACE_WRITE:
        return space_write
    return full_access


def opencode_permission_json(tier: PermissionTier) -> str:
    """Build OpenCode permission JSON from one safety tier."""

    if tier is PermissionTier.READ_ONLY:
        permissions = {
            "*": "deny",
            "read": "allow",
            "grep": "allow",
            "glob": "allow",
            "list": "allow",
        }
    elif tier is PermissionTier.SPACE_WRITE:
        permissions = {
            "*": "deny",
            "read": "allow",
            "grep": "allow",
            "glob": "allow",
            "list": "allow",
            "edit": "allow",
            "bash": "deny",
        }
    elif tier is PermissionTier.FULL_ACCESS:
        permissions = {"*": "allow"}
    elif tier is PermissionTier.DANGER:
        logger.warning(_OPENCODE_DANGER_FALLBACK_WARNING, tier=tier.value)
        permissions = {"*": "allow"}
    else:  # pragma: no cover - enum exhaustive guard
        raise ValueError(f"Unsupported OpenCode permission tier: {tier!r}")

    return json.dumps(permissions, sort_keys=True, separators=(",", ":"))


def permission_flags_for_harness(
    harness_id: HarnessId,
    config: PermissionConfig,
) -> list[str]:
    """Translate one tier into harness-specific CLI flags."""

    tier = config.tier
    if tier is PermissionTier.DANGER:
        if not config.unsafe:
            raise ValueError("Danger tier requested without --unsafe.")
        if harness_id == HarnessId("claude"):
            return ["--dangerously-skip-permissions"]
        if harness_id == HarnessId("codex"):
            return ["--dangerously-bypass-approvals-and-sandbox"]
        # OpenCode currently has no equivalent global bypass flag.
        return []

    if harness_id == HarnessId("claude"):
        return ["--allowedTools", ",".join(_claude_allowed_tools(tier))]

    if harness_id == HarnessId("codex"):
        if tier is PermissionTier.READ_ONLY:
            return ["--sandbox", "read-only"]
        if tier is PermissionTier.SPACE_WRITE:
            return ["--sandbox", "space-write"]
        return ["--sandbox", "danger-full-access"]

    # OpenCode permission controls vary by backend provider; keep default behavior for
    # safe tiers until a stable CLI surface is available.
    return []


@dataclass(frozen=True, slots=True)
class TieredPermissionResolver:
    """PermissionResolver implementation backed by one tier config."""

    config: PermissionConfig

    def resolve_flags(self, harness_id: HarnessId) -> list[str]:
        return permission_flags_for_harness(harness_id, self.config)


@dataclass(frozen=True, slots=True)
class ExplicitToolsResolver:
    """PermissionResolver backed by an explicit tool allowlist.

    For harnesses that don't support fine-grained tool lists (Codex),
    falls back to tier-based flags using the provided fallback config.
    """

    allowed_tools: tuple[str, ...]
    fallback_config: PermissionConfig

    def resolve_flags(self, harness_id: HarnessId) -> list[str]:
        # Codex only supports --sandbox, not per-tool allowlists.
        if harness_id == HarnessId("codex"):
            return permission_flags_for_harness(harness_id, self.fallback_config)

        # Claude: emit explicit allowedTools list.
        if harness_id == HarnessId("claude"):
            return ["--allowedTools", ",".join(self.allowed_tools)]

        # OpenCode / others: no fine-grained tool allowlist support yet.
        # The tier-based path also returns [] for OpenCode (permissions are
        # applied via env vars, not CLI flags), so no fallback is needed here.
        return []


def build_permission_resolver(
    *,
    allowed_tools: tuple[str, ...],
    permission_config: PermissionConfig,
    cli_permission_override: bool,
) -> TieredPermissionResolver | ExplicitToolsResolver:
    """Pick the right resolver: explicit tools if specified, else tier-based.

    CLI --permission override always wins (forces tier-based).
    """
    if allowed_tools and not cli_permission_override:
        return ExplicitToolsResolver(
            allowed_tools=allowed_tools,
            fallback_config=permission_config,
        )
    return TieredPermissionResolver(permission_config)
