"""CLI integration checks for skills/models commands."""

from __future__ import annotations

import json


def test_skills_cli_commands_work(run_meridian) -> None:
    reindex = run_meridian(["--json", "skills", "reindex"])
    assert reindex.returncode == 0
    reindex_payload = json.loads(reindex.stdout)
    assert reindex_payload["indexed_count"] > 0

    listed = run_meridian(["--json", "skills", "list"])
    assert listed.returncode == 0
    listed_payload = json.loads(listed.stdout)
    assert listed_payload["skills"]

    searched = run_meridian(["--json", "skills", "search", "mermaid"])
    assert searched.returncode == 0
    searched_payload = json.loads(searched.stdout)
    assert any(item["name"] == "mermaid" for item in searched_payload["skills"])

    shown = run_meridian(["--json", "skills", "show", "scratchpad"])
    assert shown.returncode == 0
    shown_payload = json.loads(shown.stdout)
    assert shown_payload["name"] == "scratchpad"
    assert "Scratchpad" in shown_payload["content"]


def test_models_cli_commands_work(run_meridian) -> None:
    listed = run_meridian(["--json", "models", "list"])
    assert listed.returncode == 0
    listed_payload = json.loads(listed.stdout)
    assert listed_payload["models"]
    assert any(item["model_id"] == "gpt-5.3-codex" for item in listed_payload["models"])

    shown = run_meridian(["--json", "models", "show", "codex"])
    assert shown.returncode == 0
    shown_payload = json.loads(shown.stdout)
    assert shown_payload["model_id"] == "gpt-5.3-codex"

