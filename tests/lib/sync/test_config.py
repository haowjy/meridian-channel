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


def test_sync_source_config_accepts_repo_and_local_path_variants() -> None:
    remote = SyncSourceConfig(
        name="personal",
        repo="  owner/repo  ",
        ref=" main ",
        skills=[" review ", "deploy"],
        agents=[],
        exclude_skills=[" deprecated "],
        exclude_agents=[" old-agent "],
        rename={" review ": " code-review "},
    )
    local = SyncSourceConfig(name="local_source", path=" ./skills ")

    assert remote.repo == "owner/repo"
    assert remote.ref == "main"
    assert remote.skills == ("review", "deploy")
    assert remote.agents == ()
    assert remote.exclude_skills == ("deprecated",)
    assert remote.exclude_agents == ("old-agent",)
    assert remote.rename == {"review": "code-review"}
    assert local.path == "./skills"


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


def test_load_sync_config_returns_empty_when_file_is_missing(tmp_path: Path) -> None:
    config = load_sync_config(tmp_path / ".meridian" / "config.toml")

    assert config == SyncConfig()


def test_load_sync_config_returns_empty_when_file_is_empty(tmp_path: Path) -> None:
    config_path = tmp_path / ".meridian" / "config.toml"
    _write_config(config_path, "")

    config = load_sync_config(config_path)

    assert config == SyncConfig()


def test_load_sync_config_returns_empty_when_file_has_no_sync_section(tmp_path: Path) -> None:
    config_path = tmp_path / ".meridian" / "config.toml"
    _write_config(config_path, "[defaults]\nmax_depth = 3\n")

    config = load_sync_config(config_path)

    assert config == SyncConfig()


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


def test_add_sync_source_creates_file_and_appends_without_overwriting_other_sections(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / ".meridian" / "config.toml"
    _write_config(config_path, "[defaults]\nmax_depth = 7\n")

    add_sync_source(
        config_path,
        SyncSourceConfig(
            name="personal",
            repo="owner/repo",
            ref="main",
            skills=(),
            rename={"review": "code-review"},
        ),
    )

    text = config_path.read_text(encoding="utf-8")
    assert "[defaults]\nmax_depth = 7\n" in text
    assert '[[sync.sources]]\nname = "personal"\nrepo = "owner/repo"\nref = "main"\nskills = []\n' in text
    assert 'rename = { "review" = "code-review" }\n' in text

    loaded = load_sync_config(config_path)
    assert loaded.sources == (
        SyncSourceConfig(
            name="personal",
            repo="owner/repo",
            ref="main",
            skills=(),
            rename={"review": "code-review"},
        ),
    )


def test_add_sync_source_rejects_duplicate_name(tmp_path: Path) -> None:
    config_path = tmp_path / ".meridian" / "config.toml"
    add_sync_source(config_path, SyncSourceConfig(name="personal", repo="owner/repo"))

    with pytest.raises(ValueError, match="already exists"):
        add_sync_source(config_path, SyncSourceConfig(name="personal", path="./skills"))


def test_remove_sync_source_deletes_only_target_block(tmp_path: Path) -> None:
    config_path = tmp_path / ".meridian" / "config.toml"
    _write_config(
        config_path,
        "[defaults]\nmax_depth = 5\n\n"
        "[[sync.sources]]\n"
        "name = 'personal'\n"
        "repo = 'owner/repo'\n\n"
        "[[sync.sources]]\n"
        "name = 'team'\n"
        "path = './team'\n",
    )

    remove_sync_source(config_path, "personal")

    text = config_path.read_text(encoding="utf-8")
    assert "[defaults]\nmax_depth = 5\n" in text
    assert "name = 'personal'" not in text
    assert "name = 'team'" in text
    assert load_sync_config(config_path) == SyncConfig(
        sources=(SyncSourceConfig(name="team", path="./team"),)
    )


def test_remove_sync_source_rejects_unknown_name(tmp_path: Path) -> None:
    config_path = tmp_path / ".meridian" / "config.toml"
    add_sync_source(config_path, SyncSourceConfig(name="personal", repo="owner/repo"))

    with pytest.raises(ValueError, match="not found"):
        remove_sync_source(config_path, "missing")
