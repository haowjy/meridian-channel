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


class TestExtCliIntegration:
    """Integration tests for ext CLI commands."""

    def test_ext_list_offline(self, tmp_path: Path) -> None:
        """EB3.1: ext list works with no app server."""
        result = subprocess.run(
            [sys.executable, "-m", "meridian", "ext", "list", "--format", "json"],
            capture_output=True,
            text=True,
            env=_isolated_env(tmp_path),
            check=False,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "extensions" in data

    def test_ext_commands_json(self, tmp_path: Path) -> None:
        """EB3.2: ext commands --json emits stable JSON."""
        result = subprocess.run(
            [sys.executable, "-m", "meridian", "ext", "commands", "--json"],
            capture_output=True,
            text=True,
            env=_isolated_env(tmp_path),
            check=False,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "commands" in data
        assert data["schema_version"] == 1

    def test_ext_run_invalid_json_exits_7(self, tmp_path: Path) -> None:
        """EB3.5: Invalid JSON exits with 7."""
        result = subprocess.run(
            [sys.executable, "-m", "meridian", "ext", "run", "demo.cmd", "--args", "{bad"],
            capture_output=True,
            text=True,
            env=_isolated_env(tmp_path),
            check=False,
        )
        assert result.returncode == 7

    def test_ext_run_no_server_exits_2(self, tmp_path: Path) -> None:
        """EB3.6: No server exits with 2."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "meridian",
                "ext",
                "run",
                "meridian.sessions.getSpawnStats",
                "--args",
                '{"spawn_id":"p123"}',
            ],
            capture_output=True,
            text=True,
            env=_isolated_env(tmp_path),
            check=False,
        )
        assert result.returncode == 2
