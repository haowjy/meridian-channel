"""Slice 4 config-driven streaming filter tests."""

from __future__ import annotations

from pathlib import Path

from meridian.lib.config.settings import OutputConfig, load_config
from meridian.lib.exec.terminal import (
    QUIET_VISIBLE_CATEGORIES,
    VERBOSE_VISIBLE_CATEGORIES,
    resolve_visible_categories,
)


def _write_config(repo_root: Path, content: str) -> None:
    config_path = repo_root / ".meridian" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(content, encoding="utf-8")


def test_config_preset_overrides_default_filter(tmp_path: Path) -> None:
    _write_config(
        tmp_path,
        "[output]\nverbosity = 'quiet'\n",
    )

    loaded = load_config(tmp_path)
    resolved = resolve_visible_categories(verbose=False, quiet=False, config=loaded.output)

    assert resolved == QUIET_VISIBLE_CATEGORIES


def test_cli_flags_override_config() -> None:
    config = OutputConfig(show=("system",), verbosity="quiet")

    assert (
        resolve_visible_categories(verbose=True, quiet=False, config=config)
        == VERBOSE_VISIBLE_CATEGORIES
    )
    assert (
        resolve_visible_categories(verbose=False, quiet=True, config=config)
        == QUIET_VISIBLE_CATEGORIES
    )
    assert (
        resolve_visible_categories(verbose=True, quiet=True, config=config)
        == VERBOSE_VISIBLE_CATEGORIES
    )


def test_verbosity_presets_map_correctly() -> None:
    assert resolve_visible_categories(
        verbose=False,
        quiet=False,
        config=OutputConfig(show=("assistant",), verbosity="quiet"),
    ) == QUIET_VISIBLE_CATEGORIES
    assert resolve_visible_categories(
        verbose=False,
        quiet=False,
        config=OutputConfig(show=("assistant",), verbosity="normal"),
    ) == frozenset(OutputConfig().show)
    assert resolve_visible_categories(
        verbose=False,
        quiet=False,
        config=OutputConfig(show=("assistant",), verbosity="verbose"),
    ) == VERBOSE_VISIBLE_CATEGORIES
    assert resolve_visible_categories(
        verbose=False,
        quiet=False,
        config=OutputConfig(show=("assistant",), verbosity="debug"),
    ) == VERBOSE_VISIBLE_CATEGORIES
