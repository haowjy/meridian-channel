"""Model catalog parsing and alias resolution tests."""

from __future__ import annotations

import logging
from pathlib import Path

from meridian.lib.config.catalog import load_model_catalog, resolve_model


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_resolve_model_by_alias(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _write(
        repo_root / ".meridian" / "models.toml",
        (
            "[[models]]\n"
            "model_id = 'custom-model'\n"
            "aliases = ['writer', 'quick']\n"
            "harness = 'opencode'\n"
        ),
    )

    resolved = resolve_model("writer", repo_root=repo_root)
    assert str(resolved.model_id) == "custom-model"
    assert resolved.aliases == ("writer", "quick")


def test_parse_role_and_cost_metadata_from_models_table(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _write(
        repo_root / ".meridian" / "models.toml",
        (
            "[models.custom-model]\n"
            "aliases = ['custom', 'deep']\n"
            "role = 'Deep reasoning, subtle correctness'\n"
            "strengths = 'Handles complex repository changes'\n"
            "cost_tier = '$$$'\n"
            "harness = 'claude'\n"
        ),
    )

    catalog = load_model_catalog(repo_root=repo_root)
    parsed = next(entry for entry in catalog if str(entry.model_id) == "custom-model")
    assert parsed.aliases == ("custom", "deep")
    assert parsed.role == "Deep reasoning, subtle correctness"
    assert parsed.cost_tier == "$$$"


def test_alias_collision_warns_and_uses_first_match(tmp_path: Path, caplog) -> None:
    repo_root = tmp_path / "repo"
    _write(
        repo_root / ".meridian" / "models.toml",
        (
            "[[models]]\n"
            "model_id = 'aaa-first'\n"
            "aliases = ['shared']\n"
            "harness = 'codex'\n"
            "\n"
            "[[models]]\n"
            "model_id = 'zzz-second'\n"
            "aliases = ['shared']\n"
            "harness = 'opencode'\n"
        ),
    )

    with caplog.at_level(logging.WARNING, logger="meridian.lib.config.catalog"):
        resolved = resolve_model("shared", repo_root=repo_root)

    assert str(resolved.model_id) == "aaa-first"
    assert any(
        "Model alias 'shared' is declared by 'aaa-first' and 'zzz-second'. Using 'aaa-first'."
        in message
        for message in caplog.messages
    )
