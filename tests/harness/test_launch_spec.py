"""Resolved launch spec tests for harness adapters."""

import pytest

from meridian.lib.core.types import ModelId
from meridian.lib.harness.adapter import SpawnParams, SubprocessHarness
from meridian.lib.harness.claude import ClaudeAdapter
from meridian.lib.harness.codex import CodexAdapter
from meridian.lib.harness.launch_spec import _SPEC_HANDLED_FIELDS
from meridian.lib.harness.opencode import OpenCodeAdapter
from meridian.lib.safety.permissions import PermissionConfig, TieredPermissionResolver


def _resolver(*, sandbox: str | None = None, approval: str = "default") -> TieredPermissionResolver:
    return TieredPermissionResolver(config=PermissionConfig(sandbox=sandbox, approval=approval))


def test_claude_resolve_launch_spec_normalizes_effort_and_maps_fields() -> None:
    resolver = _resolver()
    run = SpawnParams(
        prompt="test prompt",
        model=ModelId("claude-sonnet-4-6"),
        effort="xhigh",
        agent="coder",
        adhoc_agent_payload='{"agent":"payload"}   ',
        continue_harness_session_id="  claude-session  ",
        continue_fork=True,
        appended_system_prompt="system-prompt",
    )

    spec = ClaudeAdapter().resolve_launch_spec(run, resolver)

    assert spec.model == "claude-sonnet-4-6"
    assert spec.effort == "max"
    assert spec.prompt == "test prompt"
    assert spec.continue_session_id == "claude-session"
    assert spec.continue_fork is True
    assert spec.appended_system_prompt == "system-prompt"
    assert spec.agents_payload == '{"agent":"payload"}'
    assert spec.agent_name == "coder"
    assert spec.permission_config == resolver.config
    assert spec.permission_resolver is resolver


def test_codex_resolve_launch_spec_uses_permission_config_values() -> None:
    resolver = _resolver(sandbox="workspace-write", approval="confirm")
    run = SpawnParams(
        prompt="test prompt",
        model=ModelId("gpt-5.3-codex"),
        effort="xhigh",
    )

    spec = CodexAdapter().resolve_launch_spec(run, resolver)

    assert spec.model == "gpt-5.3-codex"
    assert spec.effort == "xhigh"
    assert spec.approval_mode == "confirm"
    assert spec.sandbox_mode == "workspace-write"
    assert spec.permission_config == resolver.config


def test_opencode_resolve_launch_spec_strips_prefix_and_maps_fields() -> None:
    resolver = _resolver()
    run = SpawnParams(
        prompt="test prompt",
        model=ModelId("opencode-gpt-5.3-codex"),
        effort="high",
        agent="worker",
        skills=("skill-a", "skill-b"),
    )

    spec = OpenCodeAdapter().resolve_launch_spec(run, resolver)

    assert spec.model == "gpt-5.3-codex"
    assert spec.effort == "high"
    assert spec.agent_name == "worker"
    assert spec.skills == ("skill-a", "skill-b")
    assert spec.permission_config == resolver.config


@pytest.mark.parametrize(
    "adapter",
    (
        ClaudeAdapter(),
        CodexAdapter(),
        OpenCodeAdapter(),
    ),
)
def test_resolve_launch_spec_keeps_none_effort(adapter: SubprocessHarness) -> None:
    resolver = _resolver()
    run = SpawnParams(prompt="test prompt", effort=None)

    spec = adapter.resolve_launch_spec(run, resolver)

    assert spec.effort is None


def test_launch_spec_completeness_guard_matches_spawn_params() -> None:
    assert set(SpawnParams.model_fields) == _SPEC_HANDLED_FIELDS
