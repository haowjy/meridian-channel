"""Context query operations — runtime context derivation via CLI query."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from meridian.lib.config.settings import resolve_project_root
from meridian.lib.config.workspace import get_projectable_roots, resolve_workspace_snapshot
from meridian.lib.core.resolved_context import ResolvedContext
from meridian.lib.core.util import FormatContext
from meridian.lib.ops.runtime import resolve_state_root_for_read
from meridian.lib.state.paths import resolve_fs_dir


class ContextInput(BaseModel):
    """Input for context query operation."""

    model_config = ConfigDict(frozen=True)


class ContextOutput(BaseModel):
    """Output for context query operation."""

    model_config = ConfigDict(frozen=True)

    work_dir: str | None = None
    fs_dir: str
    repo_root: str
    state_root: str
    depth: int
    context_roots: list[str] = Field(default_factory=list)

    def format_text(self, ctx: FormatContext | None = None) -> str:
        _ = ctx
        lines: list[str] = []
        lines.append(f"work_dir: {self.work_dir or '(none)'}")
        lines.append(f"fs_dir: {self.fs_dir}")
        lines.append(f"repo_root: {self.repo_root}")
        lines.append(f"state_root: {self.state_root}")
        lines.append(f"depth: {self.depth}")
        if self.context_roots:
            lines.append(f"context_roots: {', '.join(self.context_roots)}")
        return "\n".join(lines)


class WorkCurrentInput(BaseModel):
    """Input for work current operation."""

    model_config = ConfigDict(frozen=True)


class WorkCurrentOutput(BaseModel):
    """Output for work current operation."""

    model_config = ConfigDict(frozen=True)

    work_dir: str | None = None

    def format_text(self, ctx: FormatContext | None = None) -> str:
        _ = ctx
        return self.work_dir or ""


@contextmanager
def _resolved_context_env_defaults(repo_root: Path, state_root: Path) -> Iterator[None]:
    """Provide repo/state env defaults so `ResolvedContext` can resolve fully."""

    original_repo_root = os.environ.get("MERIDIAN_REPO_ROOT")
    original_state_root = os.environ.get("MERIDIAN_STATE_ROOT")

    if not (original_repo_root or "").strip():
        os.environ["MERIDIAN_REPO_ROOT"] = repo_root.as_posix()
    if not (original_state_root or "").strip():
        os.environ["MERIDIAN_STATE_ROOT"] = state_root.as_posix()

    try:
        yield
    finally:
        if original_repo_root is None:
            os.environ.pop("MERIDIAN_REPO_ROOT", None)
        else:
            os.environ["MERIDIAN_REPO_ROOT"] = original_repo_root

        if original_state_root is None:
            os.environ.pop("MERIDIAN_STATE_ROOT", None)
        else:
            os.environ["MERIDIAN_STATE_ROOT"] = original_state_root


def _resolve_runtime_context(repo_root: Path, state_root: Path) -> ResolvedContext:
    """Resolve context from environment with repo/state defaults applied."""

    with _resolved_context_env_defaults(repo_root, state_root):
        return ResolvedContext.from_environment()


def context_sync(input: ContextInput) -> ContextOutput:
    """Synchronous handler for context query."""

    _ = input
    repo_root = resolve_project_root()
    state_root = resolve_state_root_for_read(repo_root)
    resolved = _resolve_runtime_context(repo_root, state_root)
    workspace_snapshot = resolve_workspace_snapshot(repo_root)
    context_roots = [root.as_posix() for root in get_projectable_roots(workspace_snapshot)]

    return ContextOutput(
        work_dir=resolved.work_dir.as_posix() if resolved.work_dir is not None else None,
        fs_dir=resolve_fs_dir(repo_root).as_posix(),
        repo_root=repo_root.as_posix(),
        state_root=state_root.as_posix(),
        depth=resolved.depth,
        context_roots=context_roots,
    )


async def context(input: ContextInput) -> ContextOutput:
    """Async handler for context query."""

    return await asyncio.to_thread(context_sync, input)


def work_current_sync(input: WorkCurrentInput) -> WorkCurrentOutput:
    """Synchronous handler for work current query."""

    _ = input
    repo_root = resolve_project_root()
    state_root = resolve_state_root_for_read(repo_root)
    resolved = _resolve_runtime_context(repo_root, state_root)

    return WorkCurrentOutput(
        work_dir=resolved.work_dir.as_posix() if resolved.work_dir is not None else None
    )


async def work_current(input: WorkCurrentInput) -> WorkCurrentOutput:
    """Async handler for work current query."""

    return await asyncio.to_thread(work_current_sync, input)


__all__ = [
    "ContextInput",
    "ContextOutput",
    "WorkCurrentInput",
    "WorkCurrentOutput",
    "context",
    "context_sync",
    "work_current",
    "work_current_sync",
]
