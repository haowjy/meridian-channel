"""Smoke checks for mock harness behavior."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def _harness_cmd(script: Path, *args: str) -> list[str]:
    return [sys.executable, str(script), *args]


def test_mock_harness_crashes_after_requested_lines(package_root) -> None:
    script = package_root / "tests" / "mock_harness.py"
    fixture = package_root / "tests" / "fixtures" / "partial.jsonl"

    result = subprocess.run(
        _harness_cmd(script, "--stdout-file", str(fixture), "--crash-after-lines", "2"),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 70
    assert result.stdout.splitlines() == ["{\"line\": 1}", "{\"line\": 2}"]
    assert "forced crash" in result.stderr


def test_mock_harness_writes_report_and_tokens(package_root, tmp_path) -> None:
    script = package_root / "tests" / "mock_harness.py"

    result = subprocess.run(
        _harness_cmd(
            script,
            "--tokens",
            '{"input": 1500, "output": 800}',
            "--write-report",
            "Task completed successfully",
            "--report-dir",
            str(tmp_path),
            "--duration",
            "0",
        ),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["tokens"]["input"] == 1500
    report = tmp_path / "report.md"
    assert report.exists()
    assert "Task completed successfully" in report.read_text(encoding="utf-8")


def test_mock_harness_hang_flag_stays_alive_until_terminated(package_root) -> None:
    script = package_root / "tests" / "mock_harness.py"
    proc = subprocess.Popen(
        _harness_cmd(script, "--hang"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        time.sleep(0.25)
        assert proc.poll() is None
    finally:
        proc.terminate()
        proc.wait(timeout=5)
