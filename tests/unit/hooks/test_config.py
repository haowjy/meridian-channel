from __future__ import annotations

from pathlib import Path

import pytest

from meridian.lib.hooks.config import load_hooks_config


def _repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    return repo_root


def test_load_hooks_config_parses_external_and_builtin_entries(tmp_path: Path) -> None:
    repo_root = _repo(tmp_path)
    user_config = tmp_path / "user.toml"
    user_config.write_text(
        "[[hooks]]\n"
        'name = "notify"\n'
        'event = "spawn.finalized"\n'
        'command = "./scripts/notify.sh"\n'
        "\n"
        "[[hooks]]\n"
        'builtin = "git-autosync"\n',
        encoding="utf-8",
    )

    config = load_hooks_config(repo_root, user_config=user_config)

    by_name = {hook.name: hook for hook in config.hooks}
    assert set(by_name) == {"notify", "git-autosync"}
    assert by_name["notify"].command == "./scripts/notify.sh"
    assert by_name["notify"].event == "spawn.finalized"
    assert by_name["notify"].source == "user"
    assert by_name["git-autosync"].builtin == "git-autosync"
    assert by_name["git-autosync"].event == "spawn.finalized"
    assert by_name["git-autosync"].interval == "10m"


@pytest.mark.parametrize(
    ("payload", "expected_message"),
    [
        (
            "[[hooks]]\n"
            "name = 'bad'\n"
            "event = 'spawn.finalized'\n"
            "command = './a.sh'\n"
            "builtin = 'git-autosync'\n",
            "mutually exclusive",
        ),
        (
            "[[hooks]]\nname = 'bad'\nevent = 'spawn.finalized'\n",
            "expected either 'command' or 'builtin'",
        ),
        (
            "[[hooks]]\nname = 'bad'\nevent = 'spawn.unknown'\ncommand = './a.sh'\n",
            "expected one of",
        ),
        (
            "[[hooks]]\n"
            "name = 'bad'\n"
            "event = 'spawn.finalized'\n"
            "command = './a.sh'\n"
            "interval = 'ten'\n",
            "interval format",
        ),
        (
            "[[hooks]]\n"
            "builtin = 'missing-hook'\n",
            "expected one of",
        ),
    ],
)
def test_load_hooks_config_rejects_invalid_hook_definitions(
    tmp_path: Path,
    payload: str,
    expected_message: str,
) -> None:
    repo_root = _repo(tmp_path)
    (repo_root / "meridian.toml").write_text(payload, encoding="utf-8")

    with pytest.raises(ValueError, match=expected_message):
        load_hooks_config(repo_root)


def test_load_hooks_config_auto_registration_is_overridden_by_explicit_builtin(
    tmp_path: Path,
) -> None:
    repo_root = _repo(tmp_path)
    (repo_root / "meridian.toml").write_text(
        "[work.artifacts]\n"
        'sync = "git"\n'
        "\n"
        "[[hooks]]\n"
        'builtin = "git-autosync"\n'
        'event = "spawn.finalized"\n'
        'interval = "30m"\n',
        encoding="utf-8",
    )

    config = load_hooks_config(repo_root)

    assert len(config.hooks) == 1
    hook = config.hooks[0]
    assert hook.name == "git-autosync"
    assert hook.builtin == "git-autosync"
    assert hook.auto_registered is False
    assert hook.event == "spawn.finalized"
    assert hook.interval == "30m"


def test_load_hooks_config_auto_registers_git_autosync_with_builtin_defaults(
    tmp_path: Path,
) -> None:
    repo_root = _repo(tmp_path)
    (repo_root / "meridian.toml").write_text(
        "[work.artifacts]\n"
        'sync = "git"\n',
        encoding="utf-8",
    )

    config = load_hooks_config(repo_root)

    assert len(config.hooks) == 2
    by_event = {hook.event: hook for hook in config.hooks}
    assert set(by_event) == {"spawn.finalized", "work.done"}
    for hook in by_event.values():
        assert hook.name == "git-autosync"
        assert hook.builtin == "git-autosync"
        assert hook.auto_registered is True
        assert hook.interval == "10m"


def test_load_hooks_config_applies_name_override_across_sources(tmp_path: Path) -> None:
    repo_root = _repo(tmp_path)
    user_config = tmp_path / "user.toml"
    user_config.write_text(
        "[[hooks]]\n"
        'name = "sync"\n'
        'event = "spawn.finalized"\n'
        'command = "./user-sync.sh"\n',
        encoding="utf-8",
    )
    (repo_root / "meridian.toml").write_text(
        "[[hooks]]\n"
        'name = "sync"\n'
        'event = "spawn.finalized"\n'
        'command = "./project-sync.sh"\n',
        encoding="utf-8",
    )
    (repo_root / "meridian.local.toml").write_text(
        "[[hooks]]\n"
        'name = "sync"\n'
        'event = "spawn.finalized"\n'
        'command = "./local-sync.sh"\n',
        encoding="utf-8",
    )

    config = load_hooks_config(repo_root, user_config=user_config)

    assert len(config.hooks) == 1
    assert config.hooks[0].name == "sync"
    assert config.hooks[0].source == "local"
    assert config.hooks[0].command == "./local-sync.sh"
