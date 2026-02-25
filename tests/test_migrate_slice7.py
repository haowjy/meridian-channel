"""Slice 7 migration checks."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from meridian.lib.ops.migrate import MigrateRunInput, migrate_run_sync


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_migrate_imports_jsonl_idempotently_and_updates_skill_references(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"

    _write(
        repo_root / ".meridian" / "index" / "runs.jsonl",
        "\n".join(
            [
                json.dumps(
                    {
                        "run_id": "r1",
                        "status": "running",
                        "created_at_utc": "2026-02-25T10:00:00Z",
                        "model": "gpt-5.3-codex",
                        "harness": "codex",
                    }
                ),
                json.dumps(
                    {
                        "run_id": "r1",
                        "status": "succeeded",
                        "finished_at_utc": "2026-02-25T10:00:05Z",
                        "duration_seconds": 5.0,
                        "exit_code": 0,
                        "total_cost_usd": 0.12,
                        "input_tokens": 40,
                        "output_tokens": 10,
                        "model": "gpt-5.3-codex",
                        "harness": "codex",
                    }
                ),
            ]
        )
        + "\n",
    )

    _write(
        repo_root / ".agents" / "skills" / "reviewing" / "SKILL.md",
        """
        ---
        name: reviewing
        description: Review skill
        ---

        Use run-agent.sh for execution.
        """,
    )
    _write(
        repo_root / ".agents" / "skills" / "plan-slicing" / "SKILL.md",
        """
        ---
        name: plan-slicing
        description: plan skill
        ---

        Supports plan-slicing workflow.
        """,
    )
    _write(
        repo_root / ".agents" / "skills" / "researching" / "SKILL.md",
        """
        ---
        name: researching
        description: research skill
        ---

        Supports researching workflow.
        """,
    )
    _write(
        repo_root / ".agents" / "agents" / "reviewer.md",
        """
        ---
        name: reviewer
        skills: [reviewing]
        ---

        Run with run-agent.sh
        """,
    )

    first = migrate_run_sync(MigrateRunInput(repo_root=repo_root.as_posix()))
    assert first.ok is True
    assert first.imported_runs == 1
    assert set(first.renamed_skill_dirs) == {
        "plan-slicing->plan-slice",
        "reviewing->review",
        "researching->research",
    }
    assert first.updated_reference_files >= 1

    conn = sqlite3.connect(repo_root / ".meridian" / "index" / "runs.db")
    try:
        run_count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        total_cost = conn.execute(
            "SELECT total_cost_usd FROM runs WHERE id = 'r1'"
        ).fetchone()[0]
    finally:
        conn.close()

    assert run_count == 1
    assert total_cost == 0.12

    second = migrate_run_sync(MigrateRunInput(repo_root=repo_root.as_posix()))
    assert second.ok is True
    assert second.imported_runs == 0

    conn = sqlite3.connect(repo_root / ".meridian" / "index" / "runs.db")
    try:
        run_count_after = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    finally:
        conn.close()
    assert run_count_after == 1

    assert (repo_root / ".agents" / "skills" / "review" / "SKILL.md").is_file()
    assert (repo_root / ".agents" / "skills" / "plan-slice" / "SKILL.md").is_file()
    assert (repo_root / ".agents" / "skills" / "research" / "SKILL.md").is_file()

    reviewer_body = (repo_root / ".agents" / "agents" / "reviewer.md").read_text(
        encoding="utf-8"
    )
    assert "meridian run" in reviewer_body
    assert "reviewing" not in reviewer_body
    assert "review" in reviewer_body
