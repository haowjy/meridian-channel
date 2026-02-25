"""Pinned workspace context helpers."""

from __future__ import annotations

from pathlib import Path

from meridian.lib.adapters.sqlite import StateDB
from meridian.lib.domain import PinnedFile
from meridian.lib.types import WorkspaceId
from meridian.lib.workspace.crud import get_workspace_or_raise
from meridian.lib.workspace.summary import workspace_summary_path


def _summary_file(repo_root: Path, workspace_id: WorkspaceId) -> Path:
    return workspace_summary_path(repo_root, workspace_id)


def _emit_context_event(
    *,
    state: StateDB,
    workspace_id: WorkspaceId,
    event_type: str,
    file_path: str,
) -> None:
    state.append_workflow_event(
        workspace_id=workspace_id,
        event_type=event_type,
        payload={"file_path": file_path},
    )


def pin_file(
    *,
    state: StateDB,
    repo_root: Path,
    workspace_id: WorkspaceId,
    file_path: str,
) -> PinnedFile:
    """Pin one file into workspace context and emit an event."""

    get_workspace_or_raise(state, workspace_id)
    resolved_target = Path(file_path)
    if not resolved_target.is_absolute():
        resolved_target = (repo_root / resolved_target).resolve()
    state.pin_file(workspace_id, resolved_target.as_posix())
    pinned = list_pinned_files(
        state=state,
        repo_root=repo_root,
        workspace_id=workspace_id,
    )
    matched = next((item for item in pinned if item.file_path == resolved_target.as_posix()), None)
    resolved = matched.file_path if matched is not None else resolved_target.as_posix()
    _emit_context_event(
        state=state,
        workspace_id=workspace_id,
        event_type="ContextPinned",
        file_path=resolved,
    )
    return PinnedFile(workspace_id=workspace_id, file_path=resolved)


def unpin_file(
    *,
    state: StateDB,
    repo_root: Path,
    workspace_id: WorkspaceId,
    file_path: str,
) -> None:
    """Unpin one file from workspace context and emit an event."""

    get_workspace_or_raise(state, workspace_id)
    summary = _summary_file(repo_root, workspace_id).resolve().as_posix()
    target_path = Path(file_path)
    if not target_path.is_absolute():
        target_path = (repo_root / target_path).resolve()
    target = target_path.as_posix()
    if target == summary:
        raise ValueError("workspace-summary.md is always pinned and cannot be removed.")

    state.unpin_file(workspace_id, target)
    _emit_context_event(
        state=state,
        workspace_id=workspace_id,
        event_type="ContextUnpinned",
        file_path=target,
    )


def list_pinned_files(
    *,
    state: StateDB,
    repo_root: Path,
    workspace_id: WorkspaceId,
) -> tuple[PinnedFile, ...]:
    """List workspace pinned files with implicit workspace-summary pinning."""

    get_workspace_or_raise(state, workspace_id)

    summary = _summary_file(repo_root, workspace_id)
    state.pin_file(workspace_id, summary.as_posix())

    pinned = state.list_pinned_files(workspace_id)
    return tuple(
        sorted(
            pinned,
            key=lambda item: item.file_path,
        )
    )


def inject_pinned_context(
    *,
    state: StateDB,
    repo_root: Path,
    workspace_id: WorkspaceId,
) -> str:
    """Load pinned files and render concatenated context for resume prompts."""

    pinned = list_pinned_files(state=state, repo_root=repo_root, workspace_id=workspace_id)
    blocks: list[str] = []
    for item in pinned:
        path = Path(item.file_path)
        if not path.is_file():
            raise FileNotFoundError(
                "Pinned context file is missing. Unpin or restore it before resume: "
                f"{path}"
            )

        content = path.read_text(encoding="utf-8").strip()
        if not content:
            continue
        rel_path = (
            path.relative_to(repo_root).as_posix()
            if path.is_relative_to(repo_root)
            else path.as_posix()
        )
        blocks.append(f"# Pinned Context: {rel_path}\n\n{content}")

    return "\n\n".join(blocks)
