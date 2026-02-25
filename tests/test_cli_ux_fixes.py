"""Regression tests for CLI UX bug fixes in Slice A."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


def _write_skill(repo_root: Path, name: str, body: str) -> None:
    skill_file = repo_root / ".agents" / "skills" / name / "SKILL.md"
    skill_file.parent.mkdir(parents=True, exist_ok=True)
    skill_file.write_text(
        (
            "---\n"
            f"name: {name}\n"
            f"description: {name} skill\n"
            "---\n\n"
            f"{body}\n"
        ),
        encoding="utf-8",
    )


def _run_cli(
    *,
    package_root: Path,
    cli_env: dict[str, str],
    repo_root: Path,
    args: list[str],
) -> subprocess.CompletedProcess[str]:
    env = dict(cli_env)
    env["MERIDIAN_REPO_ROOT"] = repo_root.as_posix()
    return subprocess.run(
        [sys.executable, "-m", "meridian", *args],
        cwd=package_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )


def _seed_base_skills(repo_root: Path) -> None:
    _write_skill(repo_root, "run-agent", "Base run-agent skill.")
    _write_skill(repo_root, "agent", "Base agent skill.")


def test_bug5_prompt_text_uses_rendered_template_not_repr(
    package_root: Path, cli_env: dict[str, str], tmp_path: Path
) -> None:
    repo_root = tmp_path / "repo"
    _seed_base_skills(repo_root)

    result = _run_cli(
        package_root=package_root,
        cli_env=cli_env,
        repo_root=repo_root,
        args=["--json", "run", "--dry-run", "-m", "codex", "-p", "hello"],
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "dry-run"
    assert "Template(strings" not in payload["composed_prompt"]
    assert "hello" in payload["composed_prompt"]


def test_bug6_gemini_alias_routes_to_opencode(
    package_root: Path, cli_env: dict[str, str], tmp_path: Path
) -> None:
    repo_root = tmp_path / "repo"
    _seed_base_skills(repo_root)

    result = _run_cli(
        package_root=package_root,
        cli_env=cli_env,
        repo_root=repo_root,
        args=["--json", "run", "--dry-run", "-m", "gemini", "-p", "test"],
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["model"] == "gemini-3.1-pro"
    assert payload["harness_id"] == "opencode"


def test_bug8_unknown_model_warning_reports_harness_without_model_fallback(
    package_root: Path, cli_env: dict[str, str], tmp_path: Path
) -> None:
    repo_root = tmp_path / "repo"
    _seed_base_skills(repo_root)

    result = _run_cli(
        package_root=package_root,
        cli_env=cli_env,
        repo_root=repo_root,
        args=["--json", "run", "--dry-run", "-m", "nonexistent-model", "-p", "test"],
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["harness_id"] == "codex"
    warning = payload["warning"]
    assert "Unknown model family 'nonexistent-model'" in warning
    assert "Using harness 'codex'" in warning
    assert "Falling back" not in warning


def test_bug9_unknown_skill_returns_structured_error_payload(
    package_root: Path, cli_env: dict[str, str], tmp_path: Path
) -> None:
    repo_root = tmp_path / "repo"
    _seed_base_skills(repo_root)

    result = _run_cli(
        package_root=package_root,
        cli_env=cli_env,
        repo_root=repo_root,
        args=[
            "--json",
            "run",
            "--dry-run",
            "-m",
            "codex",
            "-p",
            "test",
            "--skills",
            "nonexistent-skill",
        ],
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["command"] == "run.create"
    assert payload["status"] == "failed"
    assert payload["error"] == "unknown_skills"
    assert payload["message"] == "Unknown skills: nonexistent-skill"


@pytest.mark.parametrize(
    "flag",
    ["--no-json", "--no-porcelain", "--no-yes", "--no-no-input"],
)
def test_bug3_no_prefixed_global_flags_are_accepted(
    flag: str, package_root: Path, cli_env: dict[str, str], tmp_path: Path
) -> None:
    repo_root = tmp_path / "repo"
    _seed_base_skills(repo_root)

    result = _run_cli(
        package_root=package_root,
        cli_env=cli_env,
        repo_root=repo_root,
        args=[flag, "--json", "run", "--dry-run", "-m", "codex", "-p", "hello"],
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["command"] == "run.create"
    assert payload["status"] == "dry-run"
