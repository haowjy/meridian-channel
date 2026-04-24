"""Tests for mars-based model alias loading."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from meridian.lib.catalog.model_aliases import (
    _mars_list_to_entries,
    _mars_merged_to_entries,
    entry,
    load_mars_aliases,
    load_mars_descriptions,
    run_mars_models_list_all,
    run_mars_models_resolve,
)

# --- entry() helper ---


class TestEntry:
    def test_creates_alias_entry(self) -> None:
        e = entry(alias="opus", model_id="claude-opus-4-6")
        assert e.alias == "opus"
        assert e.model_id == "claude-opus-4-6"
        assert e.resolved_harness is None

    def test_with_harness(self) -> None:
        e = entry(alias="opus", model_id="claude-opus-4-6", harness="claude")
        assert e.resolved_harness is not None
        assert str(e.resolved_harness) == "claude"

    def test_with_description(self) -> None:
        e = entry(alias="opus", model_id="claude-opus-4-6", description="A strong model.")
        assert e.description == "A strong model."


# --- _mars_list_to_entries ---


class TestMarsListToEntries:
    def test_converts_valid_entries(self) -> None:
        raw = [
            {
                "name": "opus",
                "harness": "claude",
                "mode": "pinned",
                "resolved_model": "claude-opus-4-6",
                "description": "Strong orchestrator.",
            },
            {
                "name": "gpt",
                "harness": "codex",
                "mode": "auto-resolve",
                "resolved_model": "gpt-5.4",
                "description": None,
            },
        ]
        entries = _mars_list_to_entries(raw)
        assert len(entries) == 2
        by_name = {e.alias: e for e in entries}
        assert by_name["opus"].model_id == "claude-opus-4-6"
        assert by_name["gpt"].model_id == "gpt-5.4"

    def test_skips_unresolved_aliases(self) -> None:
        raw = [
            {
                "name": "opus",
                "harness": "claude",
                "mode": "auto-resolve",
                "resolved_model": "",
                "description": "Strong orchestrator.",
            },
        ]
        entries = _mars_list_to_entries(raw)
        assert len(entries) == 0

    def test_skips_missing_name(self) -> None:
        raw = [{"harness": "claude", "resolved_model": "claude-opus-4-6"}]
        entries = _mars_list_to_entries(raw)
        assert len(entries) == 0


# --- _mars_merged_to_entries ---


class TestMarsMergedToEntries:
    def test_pinned_alias(self) -> None:
        merged = {
            "opus": {
                "harness": "claude",
                "model": "claude-opus-4-6",
                "description": "Strong.",
            },
        }
        entries = _mars_merged_to_entries(merged)
        assert len(entries) == 1
        assert entries[0].alias == "opus"
        assert entries[0].model_id == "claude-opus-4-6"
        assert entries[0].description == "Strong."

    def test_auto_resolve_skipped(self) -> None:
        merged = {
            "opus": {
                "harness": "claude",
                "provider": "anthropic",
                "match": ["opus"],
                "description": "Strong.",
            },
        }
        entries = _mars_merged_to_entries(merged)
        assert len(entries) == 0


# --- run_mars_models_resolve ---


class TestRunMarsModelsListAll:
    def test_extracts_models_and_forwards_root(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setattr(
            "meridian.lib.catalog.model_aliases._resolve_mars_binary",
            lambda: "/usr/bin/mars",
        )

        captured_cmd: list[str] = []
        captured_timeout: int | None = None

        def fake_run(
            cmd: list[str],
            *,
            capture_output: bool,
            text: bool,
            timeout: int,
        ) -> subprocess.CompletedProcess[str]:
            nonlocal captured_cmd, captured_timeout
            assert capture_output is True
            assert text is True
            captured_cmd = cmd
            captured_timeout = timeout
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout='{"models":[{"id":"gpt-5.4"}]}',
                stderr="",
            )

        monkeypatch.setattr("meridian.lib.catalog.model_aliases.subprocess.run", fake_run)

        result = run_mars_models_list_all(tmp_path)

        assert captured_cmd == [
            "/usr/bin/mars",
            "models",
            "list",
            "--all",
            "--json",
            "--root",
            str(tmp_path),
        ]
        assert captured_timeout == 60
        assert result == [{"id": "gpt-5.4"}]

    def test_returns_none_on_nonzero_exit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "meridian.lib.catalog.model_aliases._resolve_mars_binary",
            lambda: "/usr/bin/mars",
        )
        monkeypatch.setattr(
            "meridian.lib.catalog.model_aliases.subprocess.run",
            lambda *args, **kwargs: subprocess.CompletedProcess(
                args=args[0],
                returncode=2,
                stdout="",
                stderr="failed",
            ),
        )

        assert run_mars_models_list_all() is None

    def test_returns_none_on_invalid_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "meridian.lib.catalog.model_aliases._resolve_mars_binary",
            lambda: "/usr/bin/mars",
        )
        monkeypatch.setattr(
            "meridian.lib.catalog.model_aliases.subprocess.run",
            lambda *args, **kwargs: subprocess.CompletedProcess(
                args=args[0],
                returncode=0,
                stdout="{invalid",
                stderr="",
            ),
        )

        assert run_mars_models_list_all() is None

    def test_returns_none_when_models_key_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "meridian.lib.catalog.model_aliases._resolve_mars_binary",
            lambda: "/usr/bin/mars",
        )
        monkeypatch.setattr(
            "meridian.lib.catalog.model_aliases.subprocess.run",
            lambda *args, **kwargs: subprocess.CompletedProcess(
                args=args[0],
                returncode=0,
                stdout='{"aliases":[]}',
                stderr="",
            ),
        )

        assert run_mars_models_list_all() is None


# --- run_mars_models_resolve ---


class TestRunMarsModelsResolve:
    def test_returns_none_for_unknown_alias_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "meridian.lib.catalog.model_aliases._resolve_mars_binary",
            lambda: "/usr/bin/mars",
        )
        monkeypatch.setattr(
            "meridian.lib.catalog.model_aliases.subprocess.run",
            lambda *args, **kwargs: subprocess.CompletedProcess(
                args=args[0],
                returncode=1,
                stdout='{"error":"unknown alias: does-not-exist"}',
                stderr="",
            ),
        )

        assert run_mars_models_resolve("does-not-exist") is None

    def test_raises_for_non_alias_mars_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "meridian.lib.catalog.model_aliases._resolve_mars_binary",
            lambda: "/usr/bin/mars",
        )
        monkeypatch.setattr(
            "meridian.lib.catalog.model_aliases.subprocess.run",
            lambda *args, **kwargs: subprocess.CompletedProcess(
                args=args[0],
                returncode=2,
                stdout="",
                stderr='{"error":"failed to parse mars.toml"}',
            ),
        )

        with pytest.raises(RuntimeError, match=r"failed to parse mars\.toml"):
            run_mars_models_resolve("opus")


# --- load_mars_aliases ---


class TestLoadMarsAliases:
    def test_prefers_mars_cli(self) -> None:
        mars_output = [
            {
                "name": "opus",
                "harness": "claude",
                "mode": "pinned",
                "resolved_model": "claude-opus-4-6",
                "description": "Strong.",
            }
        ]
        with patch(
            "meridian.lib.catalog.model_aliases._run_mars_models_list",
            return_value=mars_output,
        ):
            result = load_mars_aliases()
            assert len(result) == 1
            assert result[0].alias == "opus"

    def test_falls_back_to_merged_file(self, tmp_path: Path) -> None:
        mars_dir = tmp_path / ".mars"
        mars_dir.mkdir()
        merged = {
            "opus": {
                "harness": "claude",
                "model": "claude-opus-4-6",
                "description": "Strong.",
            }
        }
        (mars_dir / "models-merged.json").write_text(json.dumps(merged))

        with patch(
            "meridian.lib.catalog.model_aliases._run_mars_models_list",
            return_value=None,
        ):
            result = load_mars_aliases(tmp_path)
            assert len(result) == 1
            assert result[0].alias == "opus"

    def test_returns_empty_when_no_mars(self) -> None:
        with (
            patch(
                "meridian.lib.catalog.model_aliases._run_mars_models_list",
                return_value=None,
            ),
            patch(
                "meridian.lib.catalog.model_aliases._read_mars_merged_file",
                return_value={},
            ),
        ):
            result = load_mars_aliases()
            assert result == []


# --- load_mars_descriptions ---


class TestLoadMarsDescriptions:
    def test_extracts_descriptions(self) -> None:
        mars_output = [
            {
                "name": "opus",
                "harness": "claude",
                "mode": "pinned",
                "resolved_model": "claude-opus-4-6",
                "description": "Strong orchestrator.",
            },
            {
                "name": "gpt",
                "harness": "codex",
                "mode": "pinned",
                "resolved_model": "gpt-5.4",
                "description": None,
            },
        ]
        with patch(
            "meridian.lib.catalog.model_aliases._run_mars_models_list",
            return_value=mars_output,
        ):
            descs = load_mars_descriptions()
            assert descs["claude-opus-4-6"] == "Strong orchestrator."
            assert "gpt-5.4" not in descs
