"""Config hierarchy tests for project/user/environment precedence."""

from __future__ import annotations

from pathlib import Path

import pytest

from meridian.lib.config.settings import load_config


def _write_project_config(repo_root: Path, content: str) -> None:
    config_path = repo_root / ".meridian" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(content, encoding="utf-8")


def _write_user_config(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_user_config_overrides_project_config(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _write_project_config(
        repo_root,
        "[defaults]\n"
        "max_depth = 2\n",
    )
    user_config = tmp_path / "user.toml"
    _write_user_config(
        user_config,
        "[defaults]\n"
        "max_depth = 8\n",
    )

    loaded = load_config(repo_root, user_config=user_config)

    assert loaded.max_depth == 8


def test_user_config_merges_with_project(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _write_project_config(
        repo_root,
        "[defaults]\n"
        "max_retries = 6\n"
        "\n"
        "[output]\n"
        "show = ['lifecycle', 'error']\n",
    )
    user_config = tmp_path / "user.toml"
    _write_user_config(
        user_config,
        "[defaults]\n"
        "agent = 'overlay-agent'\n"
        "\n"
        "[output]\n"
        "verbosity = 'debug'\n",
    )

    loaded = load_config(repo_root, user_config=user_config)

    assert loaded.max_retries == 6
    assert loaded.default_agent == "overlay-agent"
    assert loaded.output.show == ("lifecycle", "error")
    assert loaded.output.verbosity == "debug"


def test_user_config_missing_raises(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _write_project_config(repo_root, "")

    with pytest.raises(FileNotFoundError, match="User Meridian config file not found"):
        load_config(repo_root, user_config=tmp_path / "does-not-exist.toml")


def test_env_overrides_user_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    _write_project_config(
        repo_root,
        "[defaults]\n"
        "max_depth = 2\n",
    )
    user_config = tmp_path / "user.toml"
    _write_user_config(
        user_config,
        "[defaults]\n"
        "max_depth = 8\n",
    )
    monkeypatch.setenv("MERIDIAN_MAX_DEPTH", "11")

    loaded = load_config(repo_root, user_config=user_config)

    assert loaded.max_depth == 11


def test_meridian_config_env_var(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    _write_project_config(
        repo_root,
        "[defaults]\n"
        "max_retries = 2\n",
    )
    user_config = tmp_path / "user.toml"
    _write_user_config(
        user_config,
        "[defaults]\n"
        "max_retries = 9\n",
    )
    monkeypatch.setenv("MERIDIAN_CONFIG", user_config.as_posix())

    loaded = load_config(repo_root)

    assert loaded.max_retries == 9


def test_user_config_param_takes_precedence_over_env_var(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    _write_project_config(
        repo_root,
        "[defaults]\n"
        "max_depth = 2\n",
    )
    env_config = tmp_path / "env.toml"
    _write_user_config(
        env_config,
        "[defaults]\n"
        "max_depth = 11\n",
    )
    user_config = tmp_path / "user.toml"
    _write_user_config(
        user_config,
        "[defaults]\n"
        "max_depth = 8\n",
    )
    monkeypatch.setenv("MERIDIAN_CONFIG", env_config.as_posix())

    loaded = load_config(repo_root, user_config=user_config)

    assert loaded.max_depth == 8


def test_invalid_type_in_user_config_raises(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _write_project_config(repo_root, "")
    user_config = tmp_path / "user.toml"
    _write_user_config(
        user_config,
        "[defaults]\n"
        "max_depth = 'bad'\n",
    )

    with pytest.raises(ValueError, match="expected int"):
        load_config(repo_root, user_config=user_config)


def test_meridian_config_env_missing_file_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    _write_project_config(repo_root, "")
    missing = tmp_path / "does-not-exist.toml"
    monkeypatch.setenv("MERIDIAN_CONFIG", missing.as_posix())

    with pytest.raises(FileNotFoundError, match="User Meridian config file not found"):
        load_config(repo_root)
