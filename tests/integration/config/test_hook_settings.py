from __future__ import annotations

from pathlib import Path

import pytest

from meridian.lib.config.settings import load_config
from meridian.lib.hooks.config import load_hooks_config


def _repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    return repo_root


def test_load_hooks_config_layering_user_project_local(tmp_path: Path) -> None:
    repo_root = _repo(tmp_path)
    user_config = tmp_path / "user.toml"
    user_config.write_text(
        "[[hooks]]\n"
        'name = "notify"\n'
        'event = "spawn.finalized"\n'
        'command = "./notify-user.sh"\n'
        "\n"
        "[[hooks]]\n"
        'name = "only-user"\n'
        'event = "work.done"\n'
        'command = "./only-user.sh"\n',
        encoding="utf-8",
    )
    (repo_root / "meridian.toml").write_text(
        "[[hooks]]\n"
        'name = "notify"\n'
        'event = "spawn.finalized"\n'
        'command = "./notify-project.sh"\n',
        encoding="utf-8",
    )
    (repo_root / "meridian.local.toml").write_text(
        "[[hooks]]\n"
        'name = "notify"\n'
        'event = "spawn.finalized"\n'
        'command = "./notify-local.sh"\n',
        encoding="utf-8",
    )

    hooks = load_hooks_config(repo_root, user_config=user_config)
    by_name = {hook.name: hook for hook in hooks.hooks}

    assert by_name["notify"].source == "local"
    assert by_name["notify"].command == "./notify-local.sh"
    assert by_name["only-user"].source == "user"


def test_load_hooks_config_does_not_auto_register_git_sync_from_local_config(
    tmp_path: Path,
) -> None:
    repo_root = _repo(tmp_path)
    (repo_root / "meridian.local.toml").write_text(
        "[work.artifacts]\n"
        'sync = "git"\n',
        encoding="utf-8",
    )

    hooks = load_hooks_config(repo_root)

    assert len(hooks.hooks) == 0


def test_load_config_uses_hook_normalization_for_type_validation(tmp_path: Path) -> None:
    repo_root = _repo(tmp_path)
    (repo_root / "meridian.toml").write_text(
        "[[hooks]]\n"
        'name = "notify"\n'
        'event = "spawn.finalized"\n'
        'command = "./notify.sh"\n'
        'priority = "high"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="hooks\\[1\\]\\.priority"):
        load_config(repo_root)
