"""Workspace operations."""

from __future__ import annotations

import asyncio
import sqlite3
from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from meridian.lib.domain import WorkspaceFilters
from meridian.lib.ops._runtime import build_runtime
from meridian.lib.ops.registry import OperationSpec, operation
from meridian.lib.types import WorkspaceId
from meridian.lib.workspace import context as workspace_context
from meridian.lib.workspace import crud as workspace_crud
from meridian.lib.workspace.launch import WorkspaceLaunchRequest, launch_supervisor
from meridian.lib.workspace.summary import generate_workspace_summary

if TYPE_CHECKING:
    from meridian.lib.formatting import FormatContext


@dataclass(frozen=True, slots=True)
class WorkspaceStartInput:
    name: str | None = None
    model: str = ""
    autocompact: int | None = None
    harness_args: tuple[str, ...] = ()
    dry_run: bool = False
    repo_root: str | None = None


@dataclass(frozen=True, slots=True)
class WorkspaceResumeInput:
    workspace: str | None = None
    fresh: bool = False
    model: str = ""
    autocompact: int | None = None
    harness_args: tuple[str, ...] = ()
    repo_root: str | None = None


@dataclass(frozen=True, slots=True)
class WorkspaceListInput:
    limit: int = 10
    repo_root: str | None = None


@dataclass(frozen=True, slots=True)
class WorkspaceShowInput:
    workspace: str
    repo_root: str | None = None


@dataclass(frozen=True, slots=True)
class WorkspaceCloseInput:
    workspace: str
    repo_root: str | None = None


@dataclass(frozen=True, slots=True)
class WorkspaceActionOutput:
    workspace_id: str
    state: str
    message: str
    exit_code: int | None = None
    command: tuple[str, ...] = ()
    lock_path: str | None = None
    summary_path: str | None = None

    def format_text(self, ctx: FormatContext | None = None) -> str:
        """Single-line action summary for text output mode."""
        return f"Workspace {self.workspace_id} {self.state} ({self.message.rstrip('.')})"


@dataclass(frozen=True, slots=True)
class WorkspaceListEntry:
    workspace_id: str
    state: str
    name: str | None

    def as_row(self) -> list[str]:
        """Return columnar cells for tabular alignment."""
        return [self.workspace_id, self.state, self.name if self.name is not None else "-"]


@dataclass(frozen=True, slots=True)
class WorkspaceListOutput:
    workspaces: tuple[WorkspaceListEntry, ...]

    def format_text(self, ctx: FormatContext | None = None) -> str:
        """Columnar list of workspaces for text output mode."""
        if not self.workspaces:
            return "(no workspaces)"
        from meridian.cli.format_helpers import tabular

        return tabular([entry.as_row() for entry in self.workspaces])


@dataclass(frozen=True, slots=True)
class WorkspaceDetailOutput:
    workspace_id: str
    state: str
    name: str | None
    summary_path: str | None
    pinned_files: tuple[str, ...]
    run_ids: tuple[str, ...]

    def format_text(self, ctx: FormatContext | None = None) -> str:
        """Key-value detail view for text output mode. Omits None/empty fields."""
        from meridian.cli.format_helpers import kv_block

        pairs: list[tuple[str, str | None]] = [
            ("Workspace", self.workspace_id),
            ("State", self.state),
            ("Name", self.name),
            ("Pinned", ", ".join(self.pinned_files) if self.pinned_files else None),
            ("Runs", ", ".join(self.run_ids) if self.run_ids else None),
        ]
        return kv_block(pairs)


def _summary_text(path: str) -> str:
    from pathlib import Path

    summary_path = Path(path)
    if not summary_path.is_file():
        return ""
    return summary_path.read_text(encoding="utf-8")


def workspace_start_sync(payload: WorkspaceStartInput) -> WorkspaceActionOutput:
    runtime = build_runtime(payload.repo_root)
    workspace = workspace_crud.create_workspace(runtime.state, name=payload.name)

    summary_path = generate_workspace_summary(
        state=runtime.state,
        repo_root=runtime.repo_root,
        workspace_id=workspace.workspace_id,
    )
    pinned_context = workspace_context.inject_pinned_context(
        state=runtime.state,
        repo_root=runtime.repo_root,
        workspace_id=workspace.workspace_id,
    )

    launch_result = launch_supervisor(
        repo_root=runtime.repo_root,
        request=WorkspaceLaunchRequest(
            workspace_id=workspace.workspace_id,
            model=payload.model,
            autocompact=payload.autocompact,
            passthrough_args=payload.harness_args,
            fresh=True,
            summary_text=_summary_text(summary_path.as_posix()),
            pinned_context=pinned_context,
            dry_run=payload.dry_run,
        ),
    )
    transitioned = workspace_crud.transition_workspace(
        runtime.state,
        workspace.workspace_id,
        launch_result.final_state,
    )

    return WorkspaceActionOutput(
        workspace_id=str(workspace.workspace_id),
        state=transitioned.state,
        message=("Workspace launch dry-run." if payload.dry_run else "Workspace session finished."),
        exit_code=launch_result.exit_code,
        command=launch_result.command,
        lock_path=launch_result.lock_path.as_posix(),
        summary_path=summary_path.as_posix(),
    )


async def workspace_start(payload: WorkspaceStartInput) -> WorkspaceActionOutput:
    return await asyncio.to_thread(workspace_start_sync, payload)


def workspace_resume_sync(payload: WorkspaceResumeInput) -> WorkspaceActionOutput:
    runtime = build_runtime(payload.repo_root)
    workspace_id = workspace_crud.resolve_workspace_for_resume(runtime.state, payload.workspace)
    workspace = workspace_crud.get_workspace_or_raise(runtime.state, workspace_id)

    if workspace.state in {"completed", "abandoned"}:
        raise ValueError(
            f"Workspace '{workspace_id}' is terminal ({workspace.state}) and cannot resume"
        )
    transitioned_to_active = False
    if workspace.state != "active":
        workspace = workspace_crud.transition_workspace(runtime.state, workspace_id, "active")
        transitioned_to_active = True

    try:
        summary_path = generate_workspace_summary(
            state=runtime.state,
            repo_root=runtime.repo_root,
            workspace_id=workspace.workspace_id,
        )
        pinned_context = workspace_context.inject_pinned_context(
            state=runtime.state,
            repo_root=runtime.repo_root,
            workspace_id=workspace.workspace_id,
        )

        launch_result = launch_supervisor(
            repo_root=runtime.repo_root,
            request=WorkspaceLaunchRequest(
                workspace_id=workspace.workspace_id,
                model=payload.model,
                autocompact=payload.autocompact,
                passthrough_args=payload.harness_args,
                fresh=payload.fresh,
                summary_text=_summary_text(summary_path.as_posix()),
                pinned_context=pinned_context,
            ),
        )
    except Exception:
        # Keep lifecycle consistent when preflight fails after we set active for this resume call.
        if transitioned_to_active:
            with suppress(Exception):
                workspace_crud.transition_workspace(runtime.state, workspace_id, "paused")
        raise

    transitioned = workspace_crud.transition_workspace(
        runtime.state,
        workspace.workspace_id,
        launch_result.final_state,
    )

    return WorkspaceActionOutput(
        workspace_id=str(workspace.workspace_id),
        state=transitioned.state,
        message=("Workspace resumed (fresh)." if payload.fresh else "Workspace resumed."),
        exit_code=launch_result.exit_code,
        command=launch_result.command,
        lock_path=launch_result.lock_path.as_posix(),
        summary_path=summary_path.as_posix(),
    )


async def workspace_resume(payload: WorkspaceResumeInput) -> WorkspaceActionOutput:
    return await asyncio.to_thread(workspace_resume_sync, payload)


def workspace_list_sync(payload: WorkspaceListInput) -> WorkspaceListOutput:
    runtime = build_runtime(payload.repo_root)
    summaries = runtime.state.list_workspaces(WorkspaceFilters())
    limit = payload.limit if payload.limit > 0 else 10
    return WorkspaceListOutput(
        workspaces=tuple(
            WorkspaceListEntry(
                workspace_id=str(workspace.workspace_id),
                state=workspace.state,
                name=workspace.name,
            )
            for workspace in summaries[:limit]
        )
    )


async def workspace_list(payload: WorkspaceListInput) -> WorkspaceListOutput:
    return await asyncio.to_thread(workspace_list_sync, payload)


def workspace_show_sync(payload: WorkspaceShowInput) -> WorkspaceDetailOutput:
    runtime = build_runtime(payload.repo_root)
    workspace_id = WorkspaceId(payload.workspace.strip())
    workspace = workspace_crud.get_workspace_or_raise(runtime.state, workspace_id)

    pinned = workspace_context.list_pinned_files(
        state=runtime.state,
        repo_root=runtime.repo_root,
        workspace_id=workspace_id,
    )

    conn = sqlite3.connect(runtime.state.paths.db_path)
    conn.row_factory = sqlite3.Row
    try:
        runs = conn.execute(
            "SELECT id FROM runs WHERE workspace_id = ? ORDER BY started_at DESC",
            (str(workspace_id),),
        ).fetchall()
        summary_row = conn.execute(
            "SELECT summary_path FROM workspaces WHERE id = ?",
            (str(workspace_id),),
        ).fetchone()
    finally:
        conn.close()

    summary_path: str | None = None
    if summary_row is not None:
        summary_path = cast("str | None", summary_row["summary_path"])

    return WorkspaceDetailOutput(
        workspace_id=str(workspace.workspace_id),
        state=workspace.state,
        name=workspace.name,
        summary_path=summary_path,
        pinned_files=tuple(item.file_path for item in pinned),
        run_ids=tuple(str(row["id"]) for row in runs),
    )


async def workspace_show(payload: WorkspaceShowInput) -> WorkspaceDetailOutput:
    return await asyncio.to_thread(workspace_show_sync, payload)


def workspace_close_sync(payload: WorkspaceCloseInput) -> WorkspaceActionOutput:
    runtime = build_runtime(payload.repo_root)
    workspace_id = WorkspaceId(payload.workspace.strip())

    transitioned = workspace_crud.transition_workspace(runtime.state, workspace_id, "completed")
    summary_path = generate_workspace_summary(
        state=runtime.state,
        repo_root=runtime.repo_root,
        workspace_id=workspace_id,
    )
    return WorkspaceActionOutput(
        workspace_id=str(workspace_id),
        state=transitioned.state,
        message="Workspace closed.",
        summary_path=summary_path.as_posix(),
    )


async def workspace_close(payload: WorkspaceCloseInput) -> WorkspaceActionOutput:
    return await asyncio.to_thread(workspace_close_sync, payload)


operation(
    OperationSpec[WorkspaceStartInput, WorkspaceActionOutput](
        name="workspace.start",
        handler=workspace_start,
        sync_handler=workspace_start_sync,
        input_type=WorkspaceStartInput,
        output_type=WorkspaceActionOutput,
        cli_group="workspace",
        cli_name="start",
        mcp_name="workspace_start",
        description="Create a workspace and launch supervisor harness.",
    )
)

operation(
    OperationSpec[WorkspaceResumeInput, WorkspaceActionOutput](
        name="workspace.resume",
        handler=workspace_resume,
        sync_handler=workspace_resume_sync,
        input_type=WorkspaceResumeInput,
        output_type=WorkspaceActionOutput,
        cli_group="workspace",
        cli_name="resume",
        mcp_name="workspace_resume",
        description="Resume a workspace.",
    )
)

operation(
    OperationSpec[WorkspaceListInput, WorkspaceListOutput](
        name="workspace.list",
        handler=workspace_list,
        sync_handler=workspace_list_sync,
        input_type=WorkspaceListInput,
        output_type=WorkspaceListOutput,
        cli_group="workspace",
        cli_name="list",
        mcp_name="workspace_list",
        description="List workspaces.",
    )
)

operation(
    OperationSpec[WorkspaceShowInput, WorkspaceDetailOutput](
        name="workspace.show",
        handler=workspace_show,
        sync_handler=workspace_show_sync,
        input_type=WorkspaceShowInput,
        output_type=WorkspaceDetailOutput,
        cli_group="workspace",
        cli_name="show",
        mcp_name="workspace_show",
        description="Show workspace details.",
    )
)

operation(
    OperationSpec[WorkspaceCloseInput, WorkspaceActionOutput](
        name="workspace.close",
        handler=workspace_close,
        sync_handler=workspace_close_sync,
        input_type=WorkspaceCloseInput,
        output_type=WorkspaceActionOutput,
        cli_group="workspace",
        cli_name="close",
        mcp_name="workspace_close",
        description="Close a workspace.",
    )
)
