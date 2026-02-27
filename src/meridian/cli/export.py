"""CLI command handlers for export operations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Annotated, Any

from cyclopts import App, Parameter

from meridian.lib.ops._runtime import build_runtime
from meridian.lib.types import WorkspaceId
from meridian.lib.workspace import crud as workspace_crud
from meridian.lib.workspace.summary import collect_workspace_markdown_artifacts

Emitter = Callable[[Any], None]


@dataclass(frozen=True, slots=True)
class ExportWorkspaceOutput:
    command: str
    workspace_id: str
    artifact_paths: tuple[str, ...]


def export_workspace_sync(
    *,
    workspace: str | None = None,
    repo_root: str | None = None,
) -> ExportWorkspaceOutput:
    runtime = build_runtime(repo_root)
    workspace_id = workspace_crud.resolve_workspace_for_resume(runtime.state, workspace)
    artifacts = collect_workspace_markdown_artifacts(
        state=runtime.state,
        repo_root=runtime.repo_root,
        workspace_id=WorkspaceId(str(workspace_id)),
    )

    relative_paths: list[str] = []
    for artifact in artifacts:
        path = Path(artifact)
        rel = path.relative_to(runtime.repo_root).as_posix()
        relative_paths.append(rel)

    return ExportWorkspaceOutput(
        command="export.workspace",
        workspace_id=str(workspace_id),
        artifact_paths=tuple(relative_paths),
    )


def _export_workspace(
    emit: Emitter,
    workspace: Annotated[
        str | None,
        Parameter(name="--workspace", help="Workspace id to export."),
    ] = None,
) -> None:
    emit(export_workspace_sync(workspace=workspace))


def register_export_commands(app: App, emit: Emitter) -> None:
    handler = partial(_export_workspace, emit)
    app.command(handler, name="workspace", help="Gather committable workspace markdown artifacts.")
    app.default(handler)
