"""Integration tests for ext CLI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _isolated_env(tmp_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["MERIDIAN_HOME"] = (tmp_path / "meridian-home").as_posix()
    env["MERIDIAN_PROJECT_DIR"] = (tmp_path / "project").as_posix()
    return env


def _run_ext(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "meridian", "ext", *args],
        capture_output=True,
        text=True,
        env=_isolated_env(tmp_path),
        check=False,
    )


class TestExtCliIntegration:
    """Integration tests for ext CLI commands."""

    def test_ext_commands_json_has_expected_shape_and_cli_surface(self, tmp_path: Path) -> None:
        result = _run_ext(tmp_path, "commands", "--json")

        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert set(payload.keys()) == {"schema_version", "manifest_hash", "commands"}
        assert payload["schema_version"] == 1

        assert payload["commands"], "expected at least one CLI command"
        first = payload["commands"][0]
        assert set(first.keys()) == {
            "fqid",
            "extension_id",
            "command_id",
            "summary",
            "surfaces",
            "requires_app_server",
        }
        assert all("cli" in command["surfaces"] for command in payload["commands"])
        assert any(command["fqid"] == "meridian.workbench.ping" for command in payload["commands"])

    def test_ext_show_returns_extension_details_offline(self, tmp_path: Path) -> None:
        text_result = _run_ext(tmp_path, "show", "meridian.workbench")
        json_result = _run_ext(tmp_path, "show", "meridian.workbench", "--format", "json")

        assert text_result.returncode == 0
        assert "Extension: meridian.workbench" in text_result.stdout
        assert "ping" in text_result.stdout

        assert json_result.returncode == 0
        payload = json.loads(json_result.stdout)
        assert payload["extension_id"] == "meridian.workbench"
        assert payload["commands"] == [
            {
                "command_id": "ping",
                "summary": "Health check for extension system",
                "surfaces": ["cli", "http", "mcp"],
                "requires_app_server": True,
            }
        ]

    def test_ext_run_invalid_json_exits_7(self, tmp_path: Path) -> None:
        result = _run_ext(tmp_path, "run", "demo.cmd", "--args", "{bad")
        assert result.returncode == 7
        assert "Invalid JSON args" in result.stderr

    def test_ext_run_no_server_exits_2(self, tmp_path: Path) -> None:
        result = _run_ext(
            tmp_path,
            "run",
            "meridian.sessions.getSpawnStats",
            "--args",
            '{"spawn_id":"p123"}',
        )
        assert result.returncode == 2
        assert "No app server running" in result.stderr
