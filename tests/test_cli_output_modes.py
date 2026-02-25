"""CLI output mode behavior for Slice C output formatting."""

from __future__ import annotations

import json


def test_porcelain_mode_outputs_stable_key_values(run_meridian) -> None:
    result = run_meridian(["--porcelain", "diag", "doctor"])
    assert result.returncode == 0
    assert "ok=True" in result.stdout
    assert "\t" in result.stdout


def test_text_mode_is_human_readable(run_meridian) -> None:
    result = run_meridian(["--format", "text", "diag", "doctor"])
    assert result.returncode == 0
    # format_text() on DiagDoctorOutput emits key: value lines, not JSON
    assert "ok:" in result.stdout
    assert "repo_root:" in result.stdout
    assert not result.stdout.strip().startswith("{")


def test_json_mode_outputs_machine_json(run_meridian) -> None:
    result = run_meridian(["--format", "json", "diag", "doctor"])
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True


def test_default_mode_uses_text_format(run_meridian) -> None:
    # No format flag — default should be "text", which calls format_text()
    result = run_meridian(["diag", "doctor"])
    assert result.returncode == 0
    assert "ok:" in result.stdout
    assert not result.stdout.strip().startswith("{")
