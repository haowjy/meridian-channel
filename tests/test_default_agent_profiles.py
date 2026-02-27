"""Slice 3 default agent profile resolution tests."""

from __future__ import annotations

from pathlib import Path

import pytest

import meridian.lib.ops.run as run_ops
import meridian.lib.safety.permissions as permission_safety
import meridian.lib.workspace.launch as workspace_launch
from meridian.lib.config._paths import bundled_agents_root
from meridian.lib.config.agent import _BUILTIN_PATH, load_agent_profile
from meridian.lib.ops.run import RunCreateInput
from meridian.lib.types import WorkspaceId
from meridian.lib.workspace.launch import WorkspaceLaunchRequest, _build_interactive_command


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_config(repo_root: Path, content: str) -> None:
    _write(repo_root / ".meridian" / "config.toml", content)


def _write_skill(repo_root: Path, name: str, body: str) -> None:
    _write(
        repo_root / ".agents" / "skills" / name / "SKILL.md",
        (
            "---\n"
            f"name: {name}\n"
            f"description: {name} skill\n"
            "---\n\n"
            f"{body}\n"
        ),
    )


def _write_agent(
    repo_root: Path,
    *,
    name: str,
    model: str,
    skills: list[str],
    sandbox: str | None = None,
    mcp_tools: list[str] | None = None,
) -> None:
    lines = [
        "---",
        f"name: {name}",
        f"model: {model}",
        f"skills: [{', '.join(skills)}]",
    ]
    if sandbox is not None:
        lines.append(f"sandbox: {sandbox}")
    if mcp_tools is not None:
        lines.append(f"mcp-tools: [{', '.join(mcp_tools)}]")
    lines.append("---")
    lines.extend(["", f"# {name}", "", "Agent body."])
    _write(repo_root / ".agents" / "agents" / f"{name}.md", "\n".join(lines) + "\n")


def _allowed_tools_from_command(command: tuple[str, ...]) -> tuple[str, ...]:
    payload = command[command.index("--allowedTools") + 1]
    return tuple(item.strip() for item in payload.split(",") if item.strip())


def _flag_count(command: tuple[str, ...], flag: str) -> int:
    return sum(1 for token in command if token == flag)


def test_run_uses_default_agent_profile_and_profile_skills(tmp_path: Path) -> None:
    _write_config(
        tmp_path,
        "[defaults]\nagent = 'reviewer'\n",
    )
    _write_agent(
        tmp_path,
        name="reviewer",
        model="gpt-5.3-codex",
        skills=["reviewing"],
        sandbox="workspace-write",
    )
    _write_skill(tmp_path, "reviewing", "Review skill content")

    result = run_ops.run_create_sync(
        RunCreateInput(
            prompt="review the changes",
            dry_run=True,
            repo_root=tmp_path.as_posix(),
        )
    )

    assert result.status == "dry-run"
    assert result.model == "gpt-5.3-codex"
    assert result.agent == "reviewer"
    assert result.skills == ("reviewing",)


def test_run_falls_back_to_legacy_defaults_when_configured_profile_missing(tmp_path: Path) -> None:
    _write_config(
        tmp_path,
        "[defaults]\nagent = 'missing-profile'\n",
    )
    _write_skill(tmp_path, "run-agent", "Run delegation skill")
    _write_skill(tmp_path, "agent", "Agent baseline skill")

    result = run_ops.run_create_sync(
        RunCreateInput(
            prompt="fallback behavior",
            model="gpt-5.3-codex",
            dry_run=True,
            repo_root=tmp_path.as_posix(),
        )
    )

    assert result.status == "dry-run"
    assert result.agent is None
    assert result.skills == ("run-agent", "agent")


def test_workspace_supervisor_profile_controls_model_skills_and_sandbox(tmp_path: Path) -> None:
    _write_config(
        tmp_path,
        "[defaults]\nsupervisor_agent = 'lead-supervisor'\n",
    )
    _write_agent(
        tmp_path,
        name="lead-supervisor",
        model="claude-sonnet-4-6",
        skills=["orchestrate"],
        sandbox="unrestricted",
    )
    _write_skill(tmp_path, "orchestrate", "Supervisor orchestration content")

    request = WorkspaceLaunchRequest(workspace_id=WorkspaceId("w1"))
    command = _build_interactive_command(
        repo_root=tmp_path,
        request=request,
        prompt="workspace prompt",
        passthrough_args=(),
    )

    assert command[command.index("--model") + 1] == "claude-sonnet-4-6"
    assert "--allowedTools" in command
    prompt_payload = command[command.index("--system-prompt") + 1]
    assert "# Supervisor Skills" in prompt_payload
    assert "Supervisor orchestration content" in prompt_payload


def test_workspace_supervisor_profile_missing_uses_default_permission_tier(tmp_path: Path) -> None:
    _write_config(
        tmp_path,
        "[defaults]\nsupervisor_agent = 'missing-supervisor'\n",
    )

    request = WorkspaceLaunchRequest(workspace_id=WorkspaceId("w1"))
    command = _build_interactive_command(
        repo_root=tmp_path,
        request=request,
        prompt="workspace prompt",
        passthrough_args=(),
    )

    assert command[command.index("--model") + 1] == "claude-opus-4-6"
    assert "--allowedTools" in command
    assert command[command.index("--system-prompt") + 1] == "workspace prompt"


def test_workspace_supervisor_profile_missing_sandbox_uses_default_permission_tier(
    tmp_path: Path,
) -> None:
    _write_config(
        tmp_path,
        (
            "[defaults]\n"
            "supervisor_agent = 'lead-supervisor'\n"
            "\n"
            "[permissions]\n"
            "default_tier = 'workspace-write'\n"
        ),
    )
    _write_agent(
        tmp_path,
        name="lead-supervisor",
        model="claude-sonnet-4-6",
        skills=["orchestrate"],
    )
    _write_skill(tmp_path, "orchestrate", "Supervisor orchestration content")

    command = _build_interactive_command(
        repo_root=tmp_path,
        request=WorkspaceLaunchRequest(workspace_id=WorkspaceId("w1")),
        prompt="workspace prompt",
        passthrough_args=(),
    )

    assert "--allowedTools" in command
    allowed_tools = _allowed_tools_from_command(command)
    assert "Edit" in allowed_tools
    assert "Write" in allowed_tools


def test_workspace_supervisor_profile_unknown_sandbox_uses_default_permission_tier_with_warning(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_config(
        tmp_path,
        (
            "[defaults]\n"
            "supervisor_agent = 'lead-supervisor'\n"
            "\n"
            "[permissions]\n"
            "default_tier = 'read-only'\n"
        ),
    )
    _write_agent(
        tmp_path,
        name="lead-supervisor",
        model="claude-sonnet-4-6",
        skills=["orchestrate"],
        sandbox="full_access",
    )
    _write_skill(tmp_path, "orchestrate", "Supervisor orchestration content")

    class _Logger:
        def __init__(self) -> None:
            self.messages: list[str] = []

        def warning(self, message: str, *args: object) -> None:
            self.messages.append(message % args if args else message)

    stub_logger = _Logger()
    monkeypatch.setattr(workspace_launch, "logger", stub_logger)

    command = _build_interactive_command(
        repo_root=tmp_path,
        request=WorkspaceLaunchRequest(workspace_id=WorkspaceId("w1")),
        prompt="workspace prompt",
        passthrough_args=(),
    )

    assert "--allowedTools" in command
    allowed_tools = _allowed_tools_from_command(command)
    assert "Edit" not in allowed_tools
    assert "Write" not in allowed_tools
    assert any(
        message
        == (
            "Agent profile 'lead-supervisor' has unsupported sandbox 'full_access'; "
            "falling back to default permission tier 'read-only'."
        )
        for message in stub_logger.messages
    )


def test_workspace_supervisor_profile_non_claude_model_raises_clear_error(tmp_path: Path) -> None:
    _write_config(
        tmp_path,
        "[defaults]\nsupervisor_agent = 'lead-supervisor'\n",
    )
    _write_agent(
        tmp_path,
        name="lead-supervisor",
        model="gpt-5.3-codex",
        skills=[],
        sandbox="workspace-write",
    )

    with pytest.raises(
        ValueError,
        match=(
            r"Workspace supervisor only supports Claude harness models. "
            "Model 'gpt-5.3-codex' routes to harness 'codex'."
        ),
    ):
        _build_interactive_command(
            repo_root=tmp_path,
            request=WorkspaceLaunchRequest(workspace_id=WorkspaceId("w1")),
            prompt="workspace prompt",
            passthrough_args=(),
        )


def test_agent_profile_parses_mcp_tools_and_defaults_to_empty_tuple(tmp_path: Path) -> None:
    _write_agent(
        tmp_path,
        name="mcp-agent",
        model="gpt-5.3-codex",
        skills=["agent"],
        mcp_tools=["run_list", "run_show"],
    )
    _write_agent(
        tmp_path,
        name="plain-agent",
        model="gpt-5.3-codex",
        skills=["agent"],
    )

    mcp_profile = load_agent_profile("mcp-agent", repo_root=tmp_path)
    plain_profile = load_agent_profile("plain-agent", repo_root=tmp_path)

    assert mcp_profile.mcp_tools == ("run_list", "run_show")
    assert plain_profile.mcp_tools == ()


def test_builtin_agent_profile_used_when_no_file_on_disk(tmp_path: Path) -> None:
    """When no agent.md exists on disk, load_agent_profile returns bundled defaults."""
    profile = load_agent_profile("agent", repo_root=tmp_path)
    bundled_root = bundled_agents_root()
    assert bundled_root is not None
    assert profile.name == "agent"
    assert profile.model == "gpt-5.3-codex"
    assert profile.sandbox == "workspace-write"
    assert profile.path == (bundled_root / "agents" / "agent.md").resolve()
    assert profile.path != _BUILTIN_PATH


def test_builtin_supervisor_profile_used_when_no_file_on_disk(tmp_path: Path) -> None:
    """When no supervisor.md exists on disk, load_agent_profile returns bundled defaults."""
    profile = load_agent_profile("supervisor", repo_root=tmp_path)
    bundled_root = bundled_agents_root()
    assert bundled_root is not None
    assert profile.name == "supervisor"
    assert profile.model == "claude-opus-4-6"
    assert profile.sandbox == "unrestricted"
    assert "supervise" in profile.skills
    assert profile.path == (bundled_root / "agents" / "supervisor.md").resolve()
    assert profile.path != _BUILTIN_PATH


def test_disk_profile_takes_precedence_over_builtin(tmp_path: Path) -> None:
    """A file on disk should shadow the built-in profile of the same name."""
    _write_agent(
        tmp_path,
        name="agent",
        model="claude-sonnet-4-6",
        skills=["custom-skill"],
        sandbox="read-only",
    )
    profile = load_agent_profile("agent", repo_root=tmp_path)
    assert profile.model == "claude-sonnet-4-6"
    assert profile.path != _BUILTIN_PATH


def test_run_uses_builtin_default_agent_when_no_profile_on_disk(tmp_path: Path) -> None:
    """run_create_sync should resolve the built-in 'agent' profile as default."""
    result = run_ops.run_create_sync(
        RunCreateInput(
            prompt="hello",
            dry_run=True,
            repo_root=tmp_path.as_posix(),
        )
    )
    assert result.status == "dry-run"
    assert result.model == "gpt-5.3-codex"
    assert result.agent == "agent"
    assert "--config" in result.cli_command
    assert any(
        token.startswith("mcp_servers.meridian.command=") for token in result.cli_command
    )
    assert any(
        token.startswith("mcp_servers.meridian.enabled_tools=") for token in result.cli_command
    )


def test_claude_command_merges_permission_and_mcp_allowed_tools(tmp_path: Path) -> None:
    _write_agent(
        tmp_path,
        name="claude-reviewer",
        model="claude-sonnet-4-6",
        skills=[],
        sandbox="workspace-write",
        mcp_tools=["run_list", "run_show"],
    )

    result = run_ops.run_create_sync(
        RunCreateInput(
            prompt="review changes",
            dry_run=True,
            agent="claude-reviewer",
            repo_root=tmp_path.as_posix(),
        )
    )

    assert result.status == "dry-run"
    assert result.harness_id == "claude"
    assert "--mcp-config" in result.cli_command
    assert _flag_count(result.cli_command, "--allowedTools") == 1
    allowed_tools = _allowed_tools_from_command(result.cli_command)
    assert "Edit" in allowed_tools
    assert "Write" in allowed_tools
    assert "mcp__meridian__run_list" in allowed_tools
    assert "mcp__meridian__run_show" in allowed_tools


def test_run_logs_warning_when_profile_sandbox_exceeds_config_default(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_config(
        tmp_path,
        (
            "[defaults]\n"
            "agent = 'unsafe-agent'\n"
            "\n"
            "[permissions]\n"
            "default_tier = 'read-only'\n"
        ),
    )
    _write_agent(
        tmp_path,
        name="unsafe-agent",
        model="gpt-5.3-codex",
        skills=["run-agent", "agent"],
        sandbox="unrestricted",
    )
    _write_skill(tmp_path, "run-agent", "Run delegation skill")
    _write_skill(tmp_path, "agent", "Agent baseline skill")

    class _Logger:
        def __init__(self) -> None:
            self.messages: list[str] = []

        def warning(self, message: str) -> None:
            self.messages.append(message)

    stub_logger = _Logger()
    monkeypatch.setattr(run_ops, "logger", stub_logger)
    monkeypatch.setattr(permission_safety, "logger", stub_logger)

    run_ops.run_create_sync(
        RunCreateInput(
            prompt="check warning",
            dry_run=True,
            repo_root=tmp_path.as_posix(),
        )
    )

    assert any(
        message
        == (
            "Agent profile 'unsafe-agent' infers full-access "
            "(config default: read-only). Use --permission to override."
        )
        for message in stub_logger.messages
    )
