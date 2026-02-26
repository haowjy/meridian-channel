"""Flag-strategy command builder tests for harness adapters."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from meridian.lib.harness.adapter import PermissionResolver, RunParams
from meridian.lib.harness.claude import ClaudeAdapter
from meridian.lib.harness.codex import CodexAdapter
from meridian.lib.harness.opencode import OpenCodeAdapter
from meridian.lib.prompt.assembly import resolve_run_defaults
from meridian.lib.types import HarnessId, ModelId


class StubPermissionResolver(PermissionResolver):
    def resolve_flags(self, harness_id: HarnessId) -> list[str]:
        return ["--perm", str(harness_id)]


def _sample_run(*, model: str) -> RunParams:
    return RunParams(
        prompt="Implement feature X.",
        model=ModelId(model),
        skills=("reviewing",),
        agent="reviewer",
        extra_args=("--json",),
    )


def test_every_run_params_field_is_mapped_for_each_adapter() -> None:
    skip = {"prompt", "extra_args"}
    required = {field.name for field in dataclasses.fields(RunParams)} - skip
    adapter_classes = (ClaudeAdapter, CodexAdapter, OpenCodeAdapter)

    for adapter_class in adapter_classes:
        mapped = set(adapter_class.STRATEGIES)
        missing = required - mapped
        assert not missing, f"{adapter_class.__name__} missing strategy for {sorted(missing)}"


def test_claude_build_command_drops_agent_and_uses_prompt_flag() -> None:
    command = ClaudeAdapter().build_command(
        _sample_run(model="claude-opus-4-6"),
        StubPermissionResolver(),
    )

    assert command == [
        "claude",
        "-p",
        "Implement feature X.",
        "--model",
        "claude-opus-4-6",
        "--perm",
        "claude",
        "--json",
    ]
    assert "--agent" not in command
    assert "--skills" not in command


def test_codex_build_command_drops_agent_and_uses_positional_prompt() -> None:
    command = CodexAdapter().build_command(
        _sample_run(model="gpt-5.3-codex"),
        StubPermissionResolver(),
    )

    assert command == [
        "codex",
        "exec",
        "--model",
        "gpt-5.3-codex",
        "--perm",
        "codex",
        "--json",
        "Implement feature X.",
    ]
    assert "--agent" not in command
    assert "--skills" not in command


def test_opencode_build_command_strips_model_prefix_and_uses_positional_prompt() -> None:
    command = OpenCodeAdapter().build_command(
        _sample_run(model="opencode-gpt-5.3-codex"),
        StubPermissionResolver(),
    )

    assert command == [
        "opencode",
        "run",
        "--model",
        "gpt-5.3-codex",
        "--perm",
        "opencode",
        "--json",
        "Implement feature X.",
    ]
    assert "--agent" not in command
    assert "--skills" not in command


def test_resolve_run_defaults_resolves_model_alias(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MERIDIAN_REPO_ROOT", str(tmp_path))

    defaults = resolve_run_defaults(
        requested_model="codex",
        requested_skills=(),
        profile=None,
    )

    assert defaults.model == "gpt-5.3-codex"
