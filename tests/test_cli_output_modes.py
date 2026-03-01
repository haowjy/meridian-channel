"""CLI output mode behavior for Slice C output formatting."""

from __future__ import annotations

import json
import subprocess
import sys


def test_porcelain_mode_outputs_stable_key_values(run_meridian) -> None:
    result = run_meridian(["--porcelain", "doctor"])
    assert result.returncode == 0
    assert "ok=" in result.stdout
    assert "\t" in result.stdout


def test_text_mode_is_human_readable(run_meridian) -> None:
    result = run_meridian(["--format", "text", "doctor"])
    assert result.returncode == 0
    # format_text() on DoctorOutput emits key: value lines, not JSON
    assert "ok:" in result.stdout
    assert "repo_root:" in result.stdout
    assert not result.stdout.strip().startswith("{")


def test_json_mode_outputs_machine_json(run_meridian) -> None:
    result = run_meridian(["--format", "json", "doctor"])
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "ok" in payload


def test_default_mode_uses_text_format(run_meridian) -> None:
    # No format flag — default should be "text", which calls format_text()
    result = run_meridian(["doctor"])
    assert result.returncode == 0
    assert "ok:" in result.stdout
    assert not result.stdout.strip().startswith("{")


def test_agent_mode_defaults_to_json(package_root, cli_env) -> None:
    env = dict(cli_env)
    env["MERIDIAN_SPACE_ID"] = "s1"
    result = subprocess.run(
        [sys.executable, "-m", "meridian", "doctor"],
        cwd=package_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "ok" in payload
