"""Slice 4 config-driven streaming filter tests."""

from __future__ import annotations

from pathlib import Path

from meridian.lib.config.settings import OutputConfig, load_config
from meridian.lib.exec.terminal import (
    QUIET_VISIBLE_CATEGORIES,
    VERBOSE_VISIBLE_CATEGORIES,
    format_stderr_for_terminal,
    resolve_visible_categories,
    summarize_stderr,
)
from tests.helpers.fixtures import write_config as _write_config


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


def test_default_stderr_formatting_returns_concise_summary() -> None:
    stderr_text = "debug line\nERROR: request failed after retry\nnext details"
    rendered = format_stderr_for_terminal(stderr_text, verbose=False, quiet=False)
    assert rendered == "harness stderr: ERROR: request failed after retry"


def test_stderr_formatting_respects_verbose_and_quiet() -> None:
    stderr_text = "line 1\nline 2"
    assert format_stderr_for_terminal(stderr_text, verbose=True, quiet=False) == stderr_text
    assert format_stderr_for_terminal(stderr_text, verbose=False, quiet=True) is None


def test_stderr_summary_truncates_long_lines() -> None:
    long_line = "error " + ("x" * 400)
    summary = summarize_stderr(long_line, max_chars=50)
    assert summary is not None
    assert len(summary) == 50
    assert summary.endswith("...")
