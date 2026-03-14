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
                items=(
                    ItemRef(kind="agent", name="dev-orchestrator"),
                    ItemRef(kind="skill", name="dev-workflow"),
                ),
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
