from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

from meridian.plugin_api import file_lock, generate_repo_slug, get_user_state_root


def test_generate_repo_slug_handles_ssh_and_https_urls() -> None:
    assert generate_repo_slug("git@github.com:meridian-flow/meridian-cli.git") == (
        "meridian-flow-meridian-cli"
    )
    assert generate_repo_slug("https://github.com/meridian-flow/meridian-cli.git") == (
        "meridian-flow-meridian-cli"
    )


def test_generate_repo_slug_sanitizes_fallback_input() -> None:
    slug = generate_repo_slug("repo with spaces/and?symbols")

    assert slug == "repo-with-spaces-and-symbols"
    assert len(slug) <= 100


def test_get_user_state_root_honors_meridian_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("MERIDIAN_HOME", str(tmp_path / "custom-meridian-home"))

    assert get_user_state_root() == tmp_path / "custom-meridian-home"


def test_file_lock_exclusive_creates_lock_and_writes_pid(tmp_path: Path) -> None:
    lock_path = tmp_path / "locks" / "plugin-api.lock"

    with file_lock(lock_path, timeout=1.0, mode="exclusive"):
        assert lock_path.exists()
        assert lock_path.read_text(encoding="utf-8").strip() == str(os.getpid())
