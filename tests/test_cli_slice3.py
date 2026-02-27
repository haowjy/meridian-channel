"""CLI integration checks for Slice 3 dry-run prompt composition."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


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


def test_run_create_dry_run_outputs_composed_prompt_and_command(
    package_root: Path, tmp_path: Path
) -> None:
    repo_root = tmp_path / "slice3-test-repo"
    (repo_root / ".agents" / "agents").mkdir(parents=True, exist_ok=True)

    _write_skill(repo_root, "run-agent", "Base run-agent skill.")
    _write_skill(repo_root, "agent", "Base agent skill.")
    _write_skill(repo_root, "reviewing", "Reviewing skill body.")
    guidance_file = (
        repo_root
        / ".agents"
        / "skills"
        / "run-agent"
        / "references"
        / "default-model-guidance.md"
    )
    guidance_file.parent.mkdir(parents=True, exist_ok=True)
    guidance_file.write_text("Prefer deterministic tests.", encoding="utf-8")

    agent_file = repo_root / ".agents" / "agents" / "reviewer.md"
    agent_file.write_text(
        (
            "---\n"
            "name: reviewer\n"
            "model: gpt-5.3-codex\n"
            "skills: [reviewing]\n"
            "---\n\n"
            "Agent profile body.\n"
        ),
        encoding="utf-8",
    )

    reference_file = repo_root / "context.md"
    reference_file.write_text("Context value: {{VALUE}}", encoding="utf-8")

    env = os.environ.copy()
    env["MERIDIAN_REPO_ROOT"] = str(repo_root)
    env["PYTHONPATH"] = str(package_root / "src")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "meridian",
            "--json",
            "run",
            "--dry-run",
            "--agent",
            "reviewer",
            "-f",
            str(reference_file),
            "--var",
            "VALUE=ok",
            "-p",
            "Implement the task.",
        ],
        cwd=package_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["command"] == "run.create"
    assert payload["status"] == "dry-run"
    assert payload["model"] == "gpt-5.3-codex"
    assert payload["harness_id"] == "codex"
    assert payload["cli_command"][0] == "codex"
    # Model guidance only injected when run-agent skill is loaded; reviewer
    # profile uses skills: [reviewing], so guidance is absent.
    assert "Prefer deterministic tests." not in payload["composed_prompt"]
    assert "Context value: ok" in payload["composed_prompt"]
    assert "Implement the task." in payload["composed_prompt"]
