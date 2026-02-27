"""Slice 4 repo-root boundary discovery tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from meridian.lib.config._paths import resolve_repo_root


def test_resolve_repo_root_stops_at_submodule_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monorepo = tmp_path / "meridian-collab"
    (monorepo / ".agents" / "skills").mkdir(parents=True, exist_ok=True)

    submodule_root = monorepo / "meridian-channel"
    submodule_root.mkdir(parents=True, exist_ok=True)
    # Worktrees/submodules use a .git file marker rather than a .git directory.
    (submodule_root / ".git").write_text(
        "gitdir: ../.git/modules/meridian-channel\n",
        encoding="utf-8",
    )

    nested = submodule_root / "src" / "meridian"
    nested.mkdir(parents=True, exist_ok=True)

    monkeypatch.delenv("MERIDIAN_REPO_ROOT", raising=False)
    monkeypatch.chdir(nested)

    assert resolve_repo_root() == submodule_root.resolve()


def test_resolve_repo_root_stops_at_filesystem_root_when_unanchored(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cwd = tmp_path / "no" / "skills" / "here"
    cwd.mkdir(parents=True, exist_ok=True)

    monkeypatch.delenv("MERIDIAN_REPO_ROOT", raising=False)
    monkeypatch.chdir(cwd)

    assert resolve_repo_root() == cwd.resolve()
