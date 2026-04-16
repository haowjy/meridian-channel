from pathlib import Path

import pytest

from meridian.lib.config.settings import load_config
from meridian.lib.ops import config as config_ops
from meridian.lib.ops.config import (
    ConfigInitInput,
    ConfigResetInput,
    ConfigSetInput,
    ConfigShowInput,
    config_init_sync,
    config_reset_sync,
    config_set_sync,
    config_show_sync,
    ensure_runtime_state_bootstrap_sync,
)


def _repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    return repo_root


def test_config_init_creates_meridian_toml_and_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = _repo(tmp_path)
    config_path = repo_root / "meridian.toml"

    def _noop_mars_init(_repo_root: Path, *, link: tuple[str, ...] = ()) -> None:
        _ = link

    monkeypatch.setattr(config_ops, "_ensure_mars_init", _noop_mars_init)

    first = config_init_sync(ConfigInitInput(repo_root=repo_root.as_posix()))
    config_path.write_text("[defaults]\nharness = \"claude\"\n", encoding="utf-8")
    second = config_init_sync(ConfigInitInput(repo_root=repo_root.as_posix()))

    assert first.created is True
    assert second.created is False
    assert first.path == config_path.as_posix()
    assert second.path == config_path.as_posix()
    assert config_path.is_file()
    assert config_path.read_text(encoding="utf-8") == "[defaults]\nharness = \"claude\"\n"


def test_runtime_bootstrap_does_not_create_meridian_toml(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = _repo(tmp_path)
    calls = {"mars_init": 0}

    def _track_mars_init(_repo_root: Path, *, link: tuple[str, ...] = ()) -> None:
        _ = link
        calls["mars_init"] += 1

    monkeypatch.setattr(config_ops, "_ensure_mars_init", _track_mars_init)

    ensure_runtime_state_bootstrap_sync(repo_root)

    assert (repo_root / ".meridian").is_dir()
    assert (repo_root / ".meridian" / ".gitignore").is_file()
    assert not (repo_root / "meridian.toml").exists()
    assert not (repo_root / ".mars").exists()
    assert not (repo_root / "mars.toml").exists()
    assert calls["mars_init"] == 0


def test_config_init_uses_env_repo_root_when_path_not_provided(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_repo_root = _repo(tmp_path)
    cwd = tmp_path / "cwd"
    cwd.mkdir()

    def _noop_mars_init(_repo_root: Path, *, link: tuple[str, ...] = ()) -> None:
        _ = link

    monkeypatch.setattr(config_ops, "_ensure_mars_init", _noop_mars_init)
    monkeypatch.setenv("MERIDIAN_REPO_ROOT", env_repo_root.as_posix())
    monkeypatch.chdir(cwd)

    result = config_init_sync(ConfigInitInput())

    assert result.path == (env_repo_root / "meridian.toml").as_posix()
    assert (env_repo_root / "meridian.toml").is_file()
    assert not (cwd / "meridian.toml").exists()


def test_config_set_requires_project_config_file(tmp_path: Path) -> None:
    repo_root = _repo(tmp_path)

    with pytest.raises(ValueError, match="no project config; run `meridian config init`"):
        config_set_sync(
            ConfigSetInput(
                repo_root=repo_root.as_posix(),
                key="defaults.model",
                value="gpt-5.4",
            )
        )


def test_config_reset_requires_project_config_file(tmp_path: Path) -> None:
    repo_root = _repo(tmp_path)

    with pytest.raises(ValueError, match="no project config; run `meridian config init`"):
        config_reset_sync(
            ConfigResetInput(
                repo_root=repo_root.as_posix(),
                key="defaults.model",
            )
        )


def test_config_show_reports_meridian_toml_path_when_absent(tmp_path: Path) -> None:
    repo_root = _repo(tmp_path)

    result = config_show_sync(ConfigShowInput(repo_root=repo_root.as_posix()))

    assert result.path == (repo_root / "meridian.toml").as_posix()


def test_config_show_and_loader_share_project_config_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = _repo(tmp_path)
    project_config = repo_root / "meridian.toml"
    project_config.write_text("[defaults]\nharness = \"claude\"\n", encoding="utf-8")
    user_config = tmp_path / "user-config.toml"
    user_config.write_text("[defaults]\nharness = \"opencode\"\n", encoding="utf-8")
    monkeypatch.setenv("MERIDIAN_CONFIG", user_config.as_posix())

    project_only = config_show_sync(ConfigShowInput(repo_root=repo_root.as_posix()))
    project_only_value = next(
        item for item in project_only.values if item.key == "defaults.harness"
    )

    assert project_only.path == project_config.as_posix()
    assert project_only_value.value == "claude"
    assert project_only_value.source == "file"
    assert load_config(repo_root).default_harness == "claude"

    monkeypatch.setenv("MERIDIAN_DEFAULT_HARNESS", "codex")

    resolved = config_show_sync(ConfigShowInput(repo_root=repo_root.as_posix()))
    resolved_value = next(item for item in resolved.values if item.key == "defaults.harness")

    assert resolved.path == project_config.as_posix()
    assert resolved_value.value == "codex"
    assert resolved_value.source == "env var"
    assert resolved_value.env_var == "MERIDIAN_DEFAULT_HARNESS"
    assert load_config(repo_root).default_harness == "codex"
