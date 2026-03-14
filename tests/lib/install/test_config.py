from pathlib import Path

import pytest

from meridian.lib.install.config import SourceConfig, SourcesConfig, load_sources_config
from meridian.lib.install.config import write_sources_config
from meridian.lib.install.types import ItemRef


def test_managed_source_config_rejects_incompatible_kind_fields() -> None:
    with pytest.raises(ValueError, match="Git sources require 'url' and must not set 'path'"):
        SourceConfig(name="team", kind="git", path="./agents")

    with pytest.raises(ValueError, match="Path sources require 'path' and must not set 'url'"):
        SourceConfig(name="local", kind="path", url="https://example.com/repo.git")


def test_managed_source_config_rejects_noncanonical_rename_keys() -> None:
    with pytest.raises(ValueError, match="expected canonical 'agent:name' or 'skill:name'"):
        SourceConfig(
            name="team",
            kind="git",
            url="https://example.com/repo.git",
            rename={"reviewer-solid": "team-reviewer"},
        )


def test_load_sources_config_roundtrips_multiple_sources(tmp_path: Path) -> None:
    config_path = tmp_path / ".meridian" / "agents.toml"
    config = SourcesConfig(
        sources=(
            SourceConfig(
                name="meridian-agents",
                kind="git",
                url="https://github.com/haowjy/meridian-agents.git",
                ref="main",
                agents=("dev-orchestrator",),
                skills=("dev-workflow",),
                rename={"agent:dev-orchestrator": "team-orchestrator"},
            ),
            SourceConfig(
                name="local",
                kind="path",
                path="./tools/agents",
            ),
        )
    )

    write_sources_config(config_path, config)
    loaded = load_sources_config(config_path)

    assert loaded == config


def test_new_format_agents_skills_roundtrip(tmp_path: Path) -> None:
    config_path = tmp_path / ".meridian" / "agents.toml"
    config = SourcesConfig(
        sources=(
            SourceConfig(
                name="meridian-agents",
                kind="git",
                url="https://github.com/haowjy/meridian-agents.git",
                ref="main",
                agents=("__meridian-orchestrator", "__meridian-subagent"),
                skills=("__meridian-orchestrate",),
            ),
        )
    )
    write_sources_config(config_path, config)
    loaded = load_sources_config(config_path)
    assert loaded == config


def test_old_format_auto_migrates_on_read(tmp_path: Path) -> None:
    config_path = tmp_path / ".meridian" / "agents.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        '[[sources]]\n'
        'name = "test"\n'
        'kind = "git"\n'
        'url = "https://example.com/repo.git"\n'
        'items = [\n'
        '  { kind = "agent", name = "orchestrator" },\n'
        '  { kind = "skill", name = "workflow" },\n'
        ']\n',
        encoding="utf-8",
    )
    loaded = load_sources_config(config_path)
    source = loaded.sources[0]
    assert source.agents == ("orchestrator",)
    assert source.skills == ("workflow",)
    assert source.items is None  # migrated away


def test_both_items_and_agents_raises() -> None:
    with pytest.raises(ValueError, match="Cannot specify both"):
        SourceConfig(
            name="test",
            kind="git",
            url="https://example.com/repo.git",
            agents=("foo",),
            items=(ItemRef(kind="agent", name="bar"),),
        )


def test_effective_items_returns_none_when_no_filter() -> None:
    source = SourceConfig(name="test", kind="git", url="https://example.com/repo.git")
    assert source.effective_items is None


def test_effective_items_builds_refs_from_agents_and_skills() -> None:
    source = SourceConfig(
        name="test",
        kind="git",
        url="https://example.com/repo.git",
        agents=("a1", "a2"),
        skills=("s1",),
    )
    refs = source.effective_items
    assert refs is not None
    assert len(refs) == 3
    assert refs[0] == ItemRef(kind="agent", name="a1")
    assert refs[1] == ItemRef(kind="agent", name="a2")
    assert refs[2] == ItemRef(kind="skill", name="s1")
