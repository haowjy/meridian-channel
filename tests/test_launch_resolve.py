"""Unit tests for shared launch resolution helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

import meridian.lib.launch_resolve as launch_resolve
from meridian.lib.config.agent import AgentProfile
from meridian.lib.launch_resolve import (
    load_agent_profile_with_fallback,
    resolve_permission_tier_from_profile,
    resolve_skills_from_profile,
)
from tests.helpers.fixtures import (
    write_agent as _write_agent,
    write_skill as _write_skill,
)

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
