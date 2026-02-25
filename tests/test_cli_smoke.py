"""Smoke tests for CLI and server entry points."""

from __future__ import annotations

import json
import subprocess
import sys

from meridian import __version__


def test_help_lists_resource_first_groups(run_meridian) -> None:
    result = run_meridian(["--help"])
    assert result.returncode == 0
    for expected in [
        "serve",
        "workspace",
        "run",
        "skills",
        "models",
        "context",
        "diag",
        "export",
        "migrate",
    ]:
        assert expected in result.stdout


def test_version_flag_prints_package_version(run_meridian) -> None:
    result = run_meridian(["--version"])
    assert result.returncode == 0
    assert __version__ in result.stdout


def test_serve_exits_cleanly_on_eof(package_root, cli_env) -> None:
    proc = subprocess.Popen(
        [sys.executable, "-m", "meridian", "serve"],
        cwd=package_root,
        env=cli_env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert proc.stdin is not None
    proc.stdin.close()
    proc.wait(timeout=5)
    assert proc.returncode == 0


def test_json_and_format_flags_output_stdout_only(run_meridian) -> None:
    result = run_meridian(["--json", "run", "--dry-run", "-p", "hello"])
    assert result.returncode == 0
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["command"] == "run.create"
    assert payload["status"] == "dry-run"

    result_format = run_meridian(["--format", "json", "start"])
    assert result_format.returncode == 0
    payload_format = json.loads(result_format.stdout)
    assert payload_format["workspace_id"].startswith("w")


def test_yes_and_no_input_flags_are_wired(run_meridian) -> None:
    result = run_meridian(
        ["--yes", "--no-input", "--json", "run", "--dry-run", "-p", "prompt text"]
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "dry-run"


def test_workspace_start_supports_dry_run(run_meridian) -> None:
    result = run_meridian(["--json", "workspace", "start", "--dry-run"])
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["message"] == "Workspace launch dry-run."
    assert payload["exit_code"] == 0
    assert "mock_harness.py" in payload["command"][1]


def test_completion_bash_emits_script(run_meridian) -> None:
    result = run_meridian(["completion", "bash"])
    assert result.returncode == 0
    assert "meridian" in result.stdout


def test_doctor_alias_invokes_diag_doctor(run_meridian) -> None:
    result = run_meridian(["--json", "doctor"])
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["repo_root"]
    assert payload["db_path"]
