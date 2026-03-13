from pathlib import Path

import pytest

from meridian.lib.sync.config import (
    SyncConfig,
    SyncSourceConfig,
    add_sync_source,
    load_sync_config,
    remove_sync_source,
)


def _write_config(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"name": "personal"}, "Exactly one of 'repo' or 'path' must be set"),
        (
            {"name": "personal", "repo": "owner/repo", "path": "./skills"},
            "Exactly one of 'repo' or 'path' must be set",
        ),
        (
            {"name": "personal", "path": "./skills", "ref": "main"},
            "'ref' is only valid with 'repo'",
        ),
        (
            {"name": "personal", "repo": "owner/repo/extra"},
            "expected GitHub shorthand in 'owner/repo' format",
        ),
        (
            {"name": "bad name", "repo": "owner/repo"},
            "expected alphanumeric characters, hyphens, or underscores",
        ),
        (
            {"name": "personal", "repo": "owner/repo", "skills": ["ok", " "]},
            "expected non-empty entries",
        ),
        (
            {"name": "personal", "repo": "owner/repo", "rename": {"": "review"}},
            "expected non-empty keys and values",
        ),
        (
            {"name": "personal", "repo": "owner/repo", "rename": {"review": " "}},
            "expected non-empty keys and values",
        ),
    ],
)
def test_sync_source_config_validation_errors(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        SyncSourceConfig(**kwargs)


def test_sync_config_rejects_duplicate_source_names() -> None:
    source = SyncSourceConfig(name="shared", repo="owner/repo")

    with pytest.raises(ValueError, match="Duplicate sync source name"):
        SyncConfig(sources=(source, source))


def test_load_sync_config_reads_multiple_sources_and_normalizes_filters(tmp_path: Path) -> None:
    config_path = tmp_path / ".meridian" / "config.toml"
    _write_config(
        config_path,
        "[defaults]\nmax_depth = 4\n\n"
        "[[sync.sources]]\n"
        "name = 'personal'\n"
        "repo = 'owner/repo'\n"
        "ref = 'main'\n"
        "skills = [' review ']\n"
        "exclude_agents = [' qa ']\n"
        "rename = { review = 'code-review' }\n\n"
        "[[sync.sources]]\n"
        "name = 'local'\n"
        "path = './shared-skills'\n"
        "agents = []\n",
    )

    config = load_sync_config(config_path)

    assert len(config.sources) == 2
    assert config.sources[0] == SyncSourceConfig(
        name="personal",
        repo="owner/repo",
        ref="main",
        skills=("review",),
        exclude_agents=("qa",),
        rename={"review": "code-review"},
    )
    assert config.sources[1] == SyncSourceConfig(
        name="local",
        path="./shared-skills",
        agents=(),
    )
