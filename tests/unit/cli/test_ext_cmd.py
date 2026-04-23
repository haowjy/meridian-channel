"""Unit tests for ext CLI commands."""

from __future__ import annotations

import json

import pytest

import meridian.cli.ext_cmd as ext_cmd
from meridian.cli.ext_cmd import ext_commands, ext_list


@pytest.fixture(autouse=True)
def _reset_ext_output_hooks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ext_cmd, "_emit", None)
    monkeypatch.setattr(ext_cmd, "_resolve_global_format", None)


class TestExtList:
    """Tests for ext list command."""

    def test_ext_list_returns_extensions(self, capsys: pytest.CaptureFixture[str]) -> None:
        """EB3.1: Works with no app server."""
        ext_list(format="json")
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "extensions" in data
        assert "manifest_hash" in data


class TestExtCommands:
    """Tests for ext commands command."""

    def test_ext_commands_json_stable(self, capsys: pytest.CaptureFixture[str]) -> None:
        """EB3.2: Stable JSON for agents."""
        ext_commands(format="json", json_output=False)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "commands" in data
        assert data["schema_version"] == 1
        fqids = [command["fqid"] for command in data["commands"]]
        assert fqids == sorted(fqids)
