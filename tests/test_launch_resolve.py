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


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_agent(repo_root: Path, *, name: str, model: str) -> None:
    _write(
        repo_root / ".agents" / "agents" / f"{name}.md",
        (
            "---\n"
            f"name: {name}\n"
            f"model: {model}\n"
            "skills: []\n"
            "---\n\n"
            f"# {name}\n"
        ),
    )


def _write_skill(repo_root: Path, *, name: str, body: str = "Skill body.") -> Path:
    skill_file = repo_root / ".agents" / "skills" / name / "SKILL.md"
    _write(
        skill_file,
        (
            "---\n"
            f"name: {name}\n"
            f"description: {name} skill\n"
            "---\n\n"
            f"{body}\n"
        ),
    )
    return skill_file


def test_load_profile_explicit_agent_loads_directly(tmp_path: Path) -> None:
    _write_agent(tmp_path, name="review-primary", model="claude-sonnet-4-6")
    _write_agent(tmp_path, name="lead-primary", model="claude-opus-4-6")

    profile = load_agent_profile_with_fallback(
        repo_root=tmp_path,
        requested_agent="review-primary",
        configured_default="lead-primary",
        fallback_name="primary",
    )

    assert profile is not None
    assert profile.name == "review-primary"
    assert profile.model == "claude-sonnet-4-6"


def test_load_profile_fallback_chain(tmp_path: Path) -> None:
    _write_agent(tmp_path, name="fallback-primary", model="claude-sonnet-4-6")

    profile = load_agent_profile_with_fallback(
        repo_root=tmp_path,
        configured_default="missing-primary",
        fallback_name="fallback-primary",
    )

    assert profile is not None
    assert profile.name == "fallback-primary"


def test_load_profile_no_profiles_returns_none(tmp_path: Path) -> None:
    profile = load_agent_profile_with_fallback(
        repo_root=tmp_path,
        configured_default="missing-default",
        fallback_name="missing-fallback",
    )

    assert profile is None


def test_load_profile_whitespace_only_requested_agent_falls_through(tmp_path: Path) -> None:
    _write_agent(tmp_path, name="configured-primary", model="claude-opus-4-6")
    _write_agent(tmp_path, name="fallback-primary", model="claude-sonnet-4-6")

    profile = load_agent_profile_with_fallback(
        repo_root=tmp_path,
        requested_agent="  ",
        configured_default="configured-primary",
        fallback_name="fallback-primary",
    )

    assert profile is not None
    assert profile.name == "configured-primary"


def test_load_profile_configured_default_equals_fallback_no_double_load(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    def _fake_load_agent_profile(
        name: str,
        *,
        repo_root: Path,
        search_paths: object | None = None,
    ) -> AgentProfile:
        calls.append(name)
        if name != "agent":
            raise FileNotFoundError(name)
        return AgentProfile(
            name="agent",
            description="",
            model="gpt-5.3-codex",
            variant=None,
            skills=(),
            allowed_tools=(),
            mcp_tools=(),
            sandbox="workspace-write",
            variant_models=(),
            body="",
            path=repo_root / ".agents" / "agents" / "agent.md",
            raw_content="",
        )

    monkeypatch.setattr(launch_resolve, "load_agent_profile", _fake_load_agent_profile)

    profile = load_agent_profile_with_fallback(
        repo_root=tmp_path,
        configured_default="agent",
        fallback_name="agent",
    )

    assert profile is not None
    assert profile.name == "agent"
    assert calls == ["agent"]


def test_resolve_skills_filters_unavailable(tmp_path: Path) -> None:
    _write_skill(tmp_path, name="reviewing")

    resolved = resolve_skills_from_profile(
        profile_skills=("reviewing", "missing-skill"),
        repo_root=tmp_path,
        readonly=True,
    )

    assert resolved.skill_names == ("reviewing",)
    assert tuple(skill.name for skill in resolved.loaded_skills) == ("reviewing",)
    assert resolved.missing_skills == ("missing-skill",)


def test_resolve_skills_builds_sources(tmp_path: Path) -> None:
    skill_file = _write_skill(tmp_path, name="orchestrate")

    resolved = resolve_skills_from_profile(
        profile_skills=("orchestrate",),
        repo_root=tmp_path,
        readonly=True,
    )

    assert resolved.skill_names == ("orchestrate",)
    assert resolved.skill_sources == {"orchestrate": skill_file.parent.resolve()}


def test_resolve_skills_empty_profile_skills(tmp_path: Path) -> None:
    resolved = resolve_skills_from_profile(
        profile_skills=(),
        repo_root=tmp_path,
        readonly=True,
    )

    assert resolved.skill_names == ()
    assert resolved.loaded_skills == ()
    assert resolved.skill_sources == {}
    assert resolved.missing_skills == ()


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
