"""Harness materialization tests for parsing and orphan cleanup edge cases."""

from pathlib import Path

import pytest

from meridian.lib.harness.materialize import (
    _extract_chat_id_from_materialized,
    cleanup_orphaned_materializations,
    materialize_for_harness,
)


@pytest.fixture
def claude_layout(tmp_path: Path) -> Path:
    agents_dir = tmp_path / ".claude" / "agents"
    skills_dir = tmp_path / ".claude" / "skills"
    agents_dir.mkdir(parents=True)
    skills_dir.mkdir(parents=True)
    return tmp_path


def _create_materialized_agent(repo_root: Path, chat_id: str, name: str) -> Path:
    path = repo_root / ".claude" / "agents" / f"__{name}-{chat_id}.md"
    path.write_text(f"---\nname: __{name}-{chat_id}\n---\n", encoding="utf-8")
    return path


def _create_materialized_skill(repo_root: Path, chat_id: str, name: str) -> Path:
    skill_dir = repo_root / ".claude" / "skills" / f"__{name}-{chat_id}"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: __{name}-{chat_id}\n---\n",
        encoding="utf-8",
    )
    return skill_dir


def test_extract_chat_id_from_materialized_name() -> None:
    assert _extract_chat_id_from_materialized("__primary-c6") == "c6"
    assert _extract_chat_id_from_materialized("__agent-c44") == "c44"
    assert _extract_chat_id_from_materialized("__primary-tmp-abc12345") == "tmp-abc12345"
    assert _extract_chat_id_from_materialized("not-a-meridian-file") is None
    assert _extract_chat_id_from_materialized("_single") is None
    assert _extract_chat_id_from_materialized("__meridian-orchestrate-c55") == "c55"


def test_cleanup_orphaned_removes_inactive_and_keeps_active(claude_layout: Path) -> None:
    _create_materialized_agent(claude_layout, "c6", "primary")
    _create_materialized_skill(claude_layout, "c6", "orchestrate")
    _create_materialized_agent(claude_layout, "c99", "primary")
    _create_materialized_skill(claude_layout, "c99", "orchestrate")

    removed = cleanup_orphaned_materializations("claude", claude_layout, frozenset({"c6"}))

    assert removed == 2
    assert (claude_layout / ".claude" / "agents" / "__primary-c6.md").exists()
    assert (claude_layout / ".claude" / "skills" / "__orchestrate-c6").exists()
    assert not (claude_layout / ".claude" / "agents" / "__primary-c99.md").exists()
    assert not (claude_layout / ".claude" / "skills" / "__orchestrate-c99").exists()


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

    (agents_dir / "__agent-c99.md").write_text("orphan agent", encoding="utf-8")
    skill_dir = skills_dir / "__skill-c99"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("orphan skill", encoding="utf-8")

    removed = cleanup_orphaned_materializations("codex", repo_root, frozenset())

    assert removed == 2
    assert not (agents_dir / "__agent-c99.md").exists()
    assert not (skills_dir / "__skill-c99").exists()


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
        chat_id="c9",
    )

    assert result.materialized_skills == ("__meridian--orchestrate",)
    skill_text = (
        claude_layout / ".claude" / "skills" / "__meridian--orchestrate" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "name: __meridian--orchestrate" in skill_text
    assert "disable-model-invocation: true" in skill_text
