"""CLI output mode behavior for Slice 5b."""

from __future__ import annotations

import json


def test_porcelain_mode_outputs_stable_key_values(run_meridian) -> None:
    result = run_meridian(["--porcelain", "diag", "doctor"])
    assert result.returncode == 0
    assert "ok=True" in result.stdout
    assert "\t" in result.stdout


def test_plain_mode_is_valid_non_json_text(run_meridian) -> None:
    result = run_meridian(["--format", "plain", "diag", "doctor"])
    assert result.returncode == 0
    assert result.stdout.strip().startswith("{")
    payload = json.loads(result.stdout)
    assert payload["ok"] is True


def test_json_mode_outputs_machine_json(run_meridian) -> None:
    result = run_meridian(["--format", "json", "diag", "doctor"])
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
