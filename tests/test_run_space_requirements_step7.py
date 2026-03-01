"""Step 7 run-space requirement behavior checks."""

from __future__ import annotations

import pytest

from meridian.lib.ops._runtime import SPACE_REQUIRED_ERROR
from meridian.lib.ops.run import RunCreateInput, RunListInput, run_create_sync, run_list_sync
from meridian.lib.space.space_file import list_spaces


def test_run_spawn_auto_creates_space_without_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.delenv("MERIDIAN_SPACE_ID", raising=False)

    result = run_create_sync(
        RunCreateInput(
            prompt="auto-create",
            model="gpt-5.3-codex",
            dry_run=True,
            repo_root=tmp_path.as_posix(),
        )
    )

    assert result.status == "dry-run"
    assert result.warning is not None
    assert "WARNING [SPACE_AUTO_CREATED]" in result.warning
    assert "MERIDIAN_SPACE_ID=s1" in result.warning
    assert len(list_spaces(tmp_path)) == 1


def test_non_spawn_commands_require_space_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.delenv("MERIDIAN_SPACE_ID", raising=False)

    with pytest.raises(ValueError, match=r"ERROR \[SPACE_REQUIRED\]") as exc_info:
        run_list_sync(RunListInput(repo_root=tmp_path.as_posix()))

    assert str(exc_info.value) == SPACE_REQUIRED_ERROR
