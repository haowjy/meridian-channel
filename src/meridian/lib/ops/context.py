"""Workspace context pin/unpin/list operations."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from meridian.lib.ops._runtime import build_runtime, require_workspace_id
from meridian.lib.ops.registry import OperationSpec, operation
from meridian.lib.workspace import context as workspace_context


@dataclass(frozen=True, slots=True)
class ContextPinInput:
    file_path: str
    workspace: str | None = None
    repo_root: str | None = None


@dataclass(frozen=True, slots=True)
class ContextUnpinInput:
    file_path: str
    workspace: str | None = None
    repo_root: str | None = None


@dataclass(frozen=True, slots=True)
class ContextListInput:
    workspace: str | None = None
    repo_root: str | None = None


@dataclass(frozen=True, slots=True)
class ContextActionOutput:
    workspace_id: str
    file_path: str
    status: str


@dataclass(frozen=True, slots=True)
class ContextListOutput:
    workspace_id: str
    files: tuple[str, ...]


def context_pin_sync(payload: ContextPinInput) -> ContextActionOutput:
    runtime = build_runtime(payload.repo_root)
    workspace_id = require_workspace_id(payload.workspace)
    pinned = workspace_context.pin_file(
        state=runtime.state,
        repo_root=runtime.repo_root,
        workspace_id=workspace_id,
        file_path=payload.file_path,
    )
    return ContextActionOutput(
        workspace_id=str(workspace_id),
        file_path=pinned.file_path,
        status="pinned",
    )


async def context_pin(payload: ContextPinInput) -> ContextActionOutput:
    return await asyncio.to_thread(context_pin_sync, payload)


def context_unpin_sync(payload: ContextUnpinInput) -> ContextActionOutput:
    runtime = build_runtime(payload.repo_root)
    workspace_id = require_workspace_id(payload.workspace)
    workspace_context.unpin_file(
        state=runtime.state,
        repo_root=runtime.repo_root,
        workspace_id=workspace_id,
        file_path=payload.file_path,
    )
    return ContextActionOutput(
        workspace_id=str(workspace_id),
        file_path=payload.file_path,
        status="unpinned",
    )


async def context_unpin(payload: ContextUnpinInput) -> ContextActionOutput:
    return await asyncio.to_thread(context_unpin_sync, payload)


def context_list_sync(payload: ContextListInput) -> ContextListOutput:
    runtime = build_runtime(payload.repo_root)
    workspace_id = require_workspace_id(payload.workspace)
    items = workspace_context.list_pinned_files(
        state=runtime.state,
        repo_root=runtime.repo_root,
        workspace_id=workspace_id,
    )
    return ContextListOutput(
        workspace_id=str(workspace_id),
        files=tuple(item.file_path for item in items),
    )


async def context_list(payload: ContextListInput) -> ContextListOutput:
    return await asyncio.to_thread(context_list_sync, payload)


operation(
    OperationSpec[ContextPinInput, ContextActionOutput](
        name="context.pin",
        handler=context_pin,
        sync_handler=context_pin_sync,
        input_type=ContextPinInput,
        output_type=ContextActionOutput,
        cli_group="context",
        cli_name="pin",
        mcp_name="context_pin",
        description="Pin a file to workspace context.",
    )
)

operation(
    OperationSpec[ContextUnpinInput, ContextActionOutput](
        name="context.unpin",
        handler=context_unpin,
        sync_handler=context_unpin_sync,
        input_type=ContextUnpinInput,
        output_type=ContextActionOutput,
        cli_group="context",
        cli_name="unpin",
        mcp_name="context_unpin",
        description="Remove a pinned context file.",
    )
)

operation(
    OperationSpec[ContextListInput, ContextListOutput](
        name="context.list",
        handler=context_list,
        sync_handler=context_list_sync,
        input_type=ContextListInput,
        output_type=ContextListOutput,
        cli_group="context",
        cli_name="list",
        mcp_name="context_list",
        description="List pinned files for a workspace.",
    )
)
