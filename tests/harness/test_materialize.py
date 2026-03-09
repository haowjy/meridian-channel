"""Harness materialization tests for parsing and orphan cleanup edge cases."""

from pathlib import Path

import pytest

from meridian.lib.harness.adapter import BaseHarnessAdapter, HarnessCapabilities, HarnessNativeLayout
from meridian.lib.harness.materialize import cleanup_orphaned_materializations, materialize_for_harness
from meridian.lib.harness.registry import HarnessRegistry
from meridian.lib.harness.session_detection import infer_harness_from_untracked_session_ref
from meridian.lib.core.types import HarnessId


class CustomHarnessAdapter(BaseHarnessAdapter):
    @property
    def id(self) -> HarnessId:
        return HarnessId("custom")

    @property
    def capabilities(self) -> HarnessCapabilities:
        return HarnessCapabilities()

    def native_layout(self) -> HarnessNativeLayout | None:
        return HarnessNativeLayout(
            agents=(".custom/agents",),
            skills=(".custom/skills",),
        )

    def owns_untracked_session(self, *, repo_root: Path, session_ref: str) -> bool:
        _ = repo_root
        return session_ref == "custom-session"


@pytest.fixture
def claude_layout(tmp_path: Path) -> Path:
    agents_dir = tmp_path / ".claude" / "agents"
    skills_dir = tmp_path / ".claude" / "skills"
    agents_dir.mkdir(parents=True)
    skills_dir.mkdir(parents=True)
    return tmp_path


def _create_materialized_agent(repo_root: Path, name: str) -> Path:
    path = repo_root / ".claude" / "agents" / f"__meridian--{name}.md"
    path.write_text(f"---\nname: __meridian--{name}\n---\n", encoding="utf-8")
    return path


def _create_materialized_skill(repo_root: Path, name: str) -> Path:
    skill_dir = repo_root / ".claude" / "skills" / f"__meridian--{name}"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: __meridian--{name}\n---\n",
        encoding="utf-8",
    )
    return skill_dir


def test_cleanup_orphaned_keeps_materialized_when_active_sessions_exist(claude_layout: Path) -> None:
    _create_materialized_agent(claude_layout, "primary")
    _create_materialized_skill(claude_layout, "orchestrate")

    removed = cleanup_orphaned_materializations(
        "claude",
        claude_layout,
        has_active_sessions=True,
    )

    assert removed == 0
    assert (claude_layout / ".claude" / "agents" / "__meridian--primary.md").exists()
    assert (claude_layout / ".claude" / "skills" / "__meridian--orchestrate").exists()


def test_cleanup_orphaned_removes_materialized_when_no_active_sessions(claude_layout: Path) -> None:
    _create_materialized_agent(claude_layout, "primary")
    _create_materialized_skill(claude_layout, "orchestrate")

    removed = cleanup_orphaned_materializations(
        "claude",
        claude_layout,
        has_active_sessions=False,
    )

    assert removed == 2
    assert not (claude_layout / ".claude" / "agents" / "__meridian--primary.md").exists()
    assert not (claude_layout / ".claude" / "skills" / "__meridian--orchestrate").exists()


def test_cleanup_orphaned_scans_global_codex_directories(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    fake_home = tmp_path / "home"
    monkeypatch.setenv("HOME", fake_home.as_posix())

    agents_dir = fake_home / ".codex" / "agents"
    skills_dir = fake_home / ".codex" / "skills"
    agents_dir.mkdir(parents=True)
    skills_dir.mkdir(parents=True)

    (agents_dir / "__meridian--agent.md").write_text("orphan agent", encoding="utf-8")
    skill_dir = skills_dir / "__meridian--skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("orphan skill", encoding="utf-8")

    removed = cleanup_orphaned_materializations("codex", repo_root, has_active_sessions=False)

    assert removed == 2
    assert not (agents_dir / "__meridian--agent.md").exists()
    assert not (skills_dir / "__meridian--skill").exists()


def test_materialized_skill_forces_disable_model_invocation(claude_layout: Path) -> None:
    source_skill_dir = claude_layout / ".agents" / "skills" / "orchestrate"
    source_skill_dir.mkdir(parents=True, exist_ok=True)
    (source_skill_dir / "SKILL.md").write_text(
        "---\nname: orchestrate\ndisable-model-invocation: false\n---\nBody\n",
        encoding="utf-8",
    )

    result = materialize_for_harness(
        agent_profile=None,
        skill_sources={"orchestrate": source_skill_dir},
        harness_id="claude",
        repo_root=claude_layout,
    )

    assert result.materialized_skills == ("__meridian--orchestrate",)
    skill_text = (
        claude_layout / ".claude" / "skills" / "__meridian--orchestrate" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "name: __meridian--orchestrate" in skill_text
    assert "disable-model-invocation: true" in skill_text


def test_materialize_and_cleanup_use_injected_registry(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    source_skill_dir = repo_root / "skills-src" / "orchestrate"
    source_skill_dir.mkdir(parents=True)
    (source_skill_dir / "SKILL.md").write_text("---\nname: orchestrate\n---\nBody\n", encoding="utf-8")

    registry = HarnessRegistry()
    registry.register(CustomHarnessAdapter())

    result = materialize_for_harness(
        agent_profile=None,
        skill_sources={"orchestrate": source_skill_dir},
        harness_id="custom",
        repo_root=repo_root,
        registry=registry,
    )

    assert result.materialized_skills == ("__meridian--orchestrate",)
    assert (repo_root / ".custom" / "skills" / "__meridian--orchestrate" / "SKILL.md").exists()

    removed = cleanup_orphaned_materializations(
        "custom",
        repo_root,
        has_active_sessions=False,
        registry=registry,
    )

    assert removed == 1
    assert not (repo_root / ".custom" / "skills" / "__meridian--orchestrate").exists()


def test_infer_harness_uses_injected_registry(tmp_path: Path) -> None:
    registry = HarnessRegistry()
    registry.register(CustomHarnessAdapter())

    assert (
        infer_harness_from_untracked_session_ref(
            tmp_path,
            "custom-session",
            registry=registry,
        )
        == "custom"
    )
