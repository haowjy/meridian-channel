from pathlib import Path

from meridian.lib.install.deps import resolve_skill_deps
from meridian.lib.install.discovery import DiscoveredItem


def _write_agent(tree: Path, name: str, skills: list[str] | None = None) -> None:
    agents_dir = tree / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    skills_yaml = ""
    if skills:
        items = ", ".join(skills)
        skills_yaml = f"skills: [{items}]\n"
    (agents_dir / f"{name}.md").write_text(
        f"---\nname: {name}\nmodel: gpt-5.3-codex\n{skills_yaml}---\nBody\n",
        encoding="utf-8",
    )


def _write_skill(tree: Path, name: str) -> None:
    skill_dir = tree / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: test\n---\nContent\n",
        encoding="utf-8",
    )


def _discover(tree: Path) -> tuple[DiscoveredItem, ...]:
    from meridian.lib.install.discovery import discover_items

    return discover_items(tree)


def test_resolve_skill_deps_finds_intra_source_skills(tmp_path: Path) -> None:
    tree = tmp_path / "source"
    _write_agent(tree, "orchestrator", skills=["orchestrate", "spawn-agent"])
    _write_skill(tree, "orchestrate")
    _write_skill(tree, "spawn-agent")

    discovered = _discover(tree)
    result = resolve_skill_deps(
        tree_path=tree,
        agent_names={"orchestrator"},
        discovered_items=discovered,
    )
    assert result == {"orchestrate", "spawn-agent"}


def test_resolve_skill_deps_warns_on_missing_skill(tmp_path: Path) -> None:
    tree = tmp_path / "source"
    _write_agent(tree, "orchestrator", skills=["missing-skill"])

    discovered = _discover(tree)
    result = resolve_skill_deps(
        tree_path=tree,
        agent_names={"orchestrator"},
        discovered_items=discovered,
    )
    assert result == set()


def test_resolve_skill_deps_ignores_agents_without_skill_field(tmp_path: Path) -> None:
    tree = tmp_path / "source"
    _write_agent(tree, "simple-agent")
    _write_skill(tree, "some-skill")

    discovered = _discover(tree)
    result = resolve_skill_deps(
        tree_path=tree,
        agent_names={"simple-agent"},
        discovered_items=discovered,
    )
    assert result == set()


def test_resolve_skill_deps_handles_multiple_agents(tmp_path: Path) -> None:
    tree = tmp_path / "source"
    _write_agent(tree, "agent-a", skills=["shared-skill", "skill-a"])
    _write_agent(tree, "agent-b", skills=["shared-skill", "skill-b"])
    _write_skill(tree, "shared-skill")
    _write_skill(tree, "skill-a")
    _write_skill(tree, "skill-b")

    discovered = _discover(tree)
    result = resolve_skill_deps(
        tree_path=tree,
        agent_names={"agent-a", "agent-b"},
        discovered_items=discovered,
    )
    assert result == {"shared-skill", "skill-a", "skill-b"}
