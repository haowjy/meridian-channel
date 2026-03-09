"""Launch-time permission resolution coverage."""

from pathlib import Path

from meridian.lib.catalog.agent import AgentProfile
from meridian.lib.launch.resolve import resolve_permission_tier_from_profile


def test_permission_tier_from_sandbox() -> None:
    profile = AgentProfile(
        name="lead-primary",
        description="",
        model="claude-sonnet-4-6",
        variant=None,
        skills=(),
        allowed_tools=(),
        mcp_tools=(),
        sandbox="danger-full-access",
        variant_models=(),
        body="",
        path=Path("lead-primary.md"),
        raw_content="",
    )

    assert resolve_permission_tier_from_profile(
        profile=profile,
        default_tier="read-only",
    ) == "full-access"
