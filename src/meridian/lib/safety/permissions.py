"""Permission tiers and harness-flag translation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum

import structlog

from meridian.lib.types import HarnessId

logger = structlog.get_logger(__name__)


class PermissionTier(StrEnum):
    """Safety tiers applied to harness command construction."""

    READ_ONLY = "read-only"
    WORKSPACE_WRITE = "workspace-write"
    FULL_ACCESS = "full-access"
    DANGER = "danger"


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


def _claude_allowed_tools(tier: PermissionTier) -> tuple[str, ...]:
    read_only = (
        "Read",
        "Glob",
        "Grep",
        "Bash(git status)",
        "Bash(git log)",
        "Bash(git diff)",
    )
    workspace_write = (
        *read_only,
        "Edit",
        "Write",
        "Bash(git add)",
        "Bash(git commit)",
    )
    full_access = (
        *workspace_write,
        "WebFetch",
        "WebSearch",
        "Bash",
    )
    if tier is PermissionTier.READ_ONLY:
        return read_only
    if tier is PermissionTier.WORKSPACE_WRITE:
        return workspace_write
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
    elif tier is PermissionTier.WORKSPACE_WRITE:
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
        logger.warning(
            "OpenCode 'danger' tier currently matches 'full-access'.",
            tier=tier.value,
        )
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
        if tier is PermissionTier.WORKSPACE_WRITE:
            return ["--sandbox", "workspace-write"]
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
