"""Permission tiers and harness-flag translation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from meridian.lib.types import HarnessId


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


def parse_permission_tier(raw: str | PermissionTier | None) -> PermissionTier:
    """Parse one permission tier string."""

    if raw is None:
        return PermissionTier.READ_ONLY
    if isinstance(raw, PermissionTier):
        return raw

    normalized = raw.strip().lower()
    if not normalized:
        return PermissionTier.READ_ONLY
    for candidate in PermissionTier:
        if candidate.value == normalized:
            return candidate
    allowed = ", ".join(item.value for item in PermissionTier)
    raise ValueError(f"Unsupported permission tier '{raw}'. Expected: {allowed}.")


def build_permission_config(
    tier: str | PermissionTier | None,
    *,
    unsafe: bool,
) -> PermissionConfig:
    """Build and validate a permission configuration."""

    resolved = PermissionConfig(tier=parse_permission_tier(tier), unsafe=unsafe)
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
