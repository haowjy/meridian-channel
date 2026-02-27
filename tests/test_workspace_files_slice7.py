"""Session workspace file operations and @ reference resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

import meridian.lib.ops.run as run_ops
from meridian.lib.ops.run import RunCreateInput
from meridian.lib.ops.workspace import (
    WorkspaceFilesInput,
    WorkspaceReadInput,
    WorkspaceWriteInput,
    workspace_files_sync,
    workspace_read_sync,
    workspace_write_sync,
)


def test_workspace_write_auto_session_then_read_and_list(tmp_path: Path) -> None:
    write = workspace_write_sync(
        WorkspaceWriteInput(
            name="@review-prompt",
            content="hello session",
            repo_root=tmp_path.as_posix(),
        )
    )

    assert write.created_session is True
    assert write.session_id
    assert write.path == f".meridian/sessions/{write.session_id}/review-prompt.md"

    session_file = tmp_path / ".meridian" / "sessions" / write.session_id / "review-prompt.md"
    assert session_file.read_text(encoding="utf-8") == "hello session"

    read = workspace_read_sync(
        WorkspaceReadInput(
            name="@review-prompt",
            session_id=write.session_id,
            repo_root=tmp_path.as_posix(),
        )
    )
    assert read.content == "hello session"

    files = workspace_files_sync(
        WorkspaceFilesInput(
            session_id=write.session_id,
            repo_root=tmp_path.as_posix(),
        )
    )
    assert [item.name for item in files.files] == ["@review-prompt"]
    assert files.files[0].size_bytes == len("hello session")


def test_workspace_file_names_enforce_flat_namespace(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="flat namespace"):
        _ = workspace_write_sync(
            WorkspaceWriteInput(
                name="@nested/file",
                content="bad",
                session_id="sess-flat",
                repo_root=tmp_path.as_posix(),
            )
        )


def test_workspace_read_and_files_require_session_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("MERIDIAN_SESSION", raising=False)

    with pytest.raises(ValueError, match="MERIDIAN_SESSION"):
        _ = workspace_read_sync(WorkspaceReadInput(name="@missing", repo_root=tmp_path.as_posix()))

    with pytest.raises(ValueError, match="MERIDIAN_SESSION"):
        _ = workspace_files_sync(WorkspaceFilesInput(repo_root=tmp_path.as_posix()))


def test_run_create_dry_run_resolves_session_reference(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    session_id = "sess-run"
    session_file = tmp_path / ".meridian" / "sessions" / session_id / "design.md"
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text("session context", encoding="utf-8")

    monkeypatch.setenv("MERIDIAN_SESSION", session_id)

    result = run_ops.run_create_sync(
        RunCreateInput(
            prompt="Use session reference",
            files=("@design",),
            dry_run=True,
            repo_root=tmp_path.as_posix(),
        )
    )

    assert result.status == "dry-run"
    assert result.reference_files == (session_file.resolve().as_posix(),)
    assert result.composed_prompt is not None
    assert "session context" in result.composed_prompt
