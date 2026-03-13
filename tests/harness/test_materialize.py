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
