from pathlib import Path

import pytest

from meridian.lib.config.settings import load_config
from meridian.lib.harness.registry import get_default_harness_registry
from meridian.lib.launch.resolve import ensure_bootstrap_ready, resolve_policies


def _write_agent(path: Path, *, name: str, model: str = "gpt-5.3-codex") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "---",
                f"name: {name}",
                "description: test agent",
                f"model: {model}",
                "sandbox: workspace-write",
                "---",
                "",
                "# Agent",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_ensure_bootstrap_ready_uses_builtin_when_configured_default_is_unmanaged(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    with pytest.raises(FileNotFoundError, match="agent:__meridian-orchestrator"):
        ensure_bootstrap_ready(
            repo_root=repo_root,
            configured_default_agent="dev-orchestration",
            requested_agent=None,
            dry_run=True,
            builtin_default_agent="__meridian-orchestrator",
        )


def test_resolve_policies_falls_back_to_builtin_default_agent_with_warning(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_agent(
        repo_root / ".agents" / "agents" / "__meridian-orchestrator.md",
        name="__meridian-orchestrator",
    )

    policies = resolve_policies(
        repo_root=repo_root,
        requested_model="",
        requested_harness=None,
        requested_agent=None,
        config=load_config(repo_root),
        harness_registry=get_default_harness_registry(),
        configured_default_agent="dev-orchestration",
        builtin_default_agent="__meridian-orchestrator",
        configured_default_harness="codex",
        skills_readonly=True,
    )

    assert policies.profile is not None
    assert policies.profile.name == "__meridian-orchestrator"
    assert policies.warning is not None
    assert "dev-orchestration" in policies.warning
    assert "__meridian-orchestrator" in policies.warning


def test_resolve_policies_does_not_fallback_explicit_missing_agent(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_agent(
        repo_root / ".agents" / "agents" / "__meridian-orchestrator.md",
        name="__meridian-orchestrator",
    )

    with pytest.raises(FileNotFoundError, match="dev-orchestration"):
        resolve_policies(
            repo_root=repo_root,
            requested_model="",
            requested_harness=None,
            requested_agent="dev-orchestration",
            config=load_config(repo_root),
            harness_registry=get_default_harness_registry(),
            configured_default_agent="__meridian-orchestrator",
            builtin_default_agent="__meridian-orchestrator",
            configured_default_harness="codex",
            skills_readonly=True,
        )
