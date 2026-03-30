import pytest

from meridian.lib.core.types import HarnessId
from meridian.lib.harness.adapter import SpawnParams
from meridian.lib.harness.claude import ClaudeAdapter
from meridian.lib.harness.opencode import OpenCodeAdapter


class _NoopResolver:
    def resolve_flags(self, harness_id: HarnessId) -> list[str]:
        _ = harness_id
        return []


@pytest.mark.parametrize(
    ("adapter", "session_flag", "fork_flag"),
    (
        (ClaudeAdapter(), "--resume", "--fork-session"),
        (OpenCodeAdapter(), "--session", "--fork"),
    ),
)
def test_build_command_appends_fork_flags_for_continuations(
    adapter: ClaudeAdapter | OpenCodeAdapter,
    session_flag: str,
    fork_flag: str,
) -> None:
    command = adapter.build_command(
        SpawnParams(
            prompt="fork run",
            continue_harness_session_id="source-session-123",
            continue_fork=True,
        ),
        _NoopResolver(),
    )

    assert session_flag in command
    assert command[command.index(session_flag) + 1] == "source-session-123"
    assert fork_flag in command


@pytest.mark.parametrize("adapter", (ClaudeAdapter(), OpenCodeAdapter()))
def test_seed_session_uses_existing_harness_session_for_fork(
    adapter: ClaudeAdapter | OpenCodeAdapter,
) -> None:
    seed = adapter.seed_session(
        is_resume=False,
        harness_session_id="source-session-123",
        passthrough_args=("--session-id", "ignored-session"),
    )

    assert seed.session_id == "source-session-123"
    assert seed.session_args == ()


def test_claude_seed_session_injects_session_id_for_fresh_launches() -> None:
    seed = ClaudeAdapter().seed_session(
        is_resume=False,
        harness_session_id="",
        passthrough_args=(),
    )

    assert seed.session_id
    assert seed.session_args == ("--session-id", seed.session_id)


@pytest.mark.parametrize("adapter", (ClaudeAdapter(), OpenCodeAdapter()))
def test_filter_launch_content_keeps_full_content_for_fork(
    adapter: ClaudeAdapter | OpenCodeAdapter,
) -> None:
    policy = adapter.filter_launch_content(
        prompt="launch prompt",
        skill_injection="skill text",
        is_resume=False,
        harness_session_id="source-session-123",
    )

    assert policy.prompt == "launch prompt"
    assert policy.skill_injection == "skill text"


@pytest.mark.parametrize(
    ("adapter", "expected_skill_injection"),
    (
        (ClaudeAdapter(), "skill text"),
        (OpenCodeAdapter(), None),
    ),
)
def test_filter_launch_content_suppresses_prompt_for_resume(
    adapter: ClaudeAdapter | OpenCodeAdapter,
    expected_skill_injection: str | None,
) -> None:
    policy = adapter.filter_launch_content(
        prompt="launch prompt",
        skill_injection="skill text",
        is_resume=True,
        harness_session_id="source-session-123",
    )

    assert policy.prompt == ""
    assert policy.skill_injection == expected_skill_injection
