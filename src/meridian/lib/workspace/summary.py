"""Workspace summary and export artifact helpers."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from meridian.lib.adapters.sqlite import StateDB
from meridian.lib.domain import Workspace
from meridian.lib.types import WorkspaceId


def workspace_summary_path(repo_root: Path, workspace_id: WorkspaceId) -> Path:
    """Return canonical workspace-summary.md path for one workspace."""

    return repo_root / ".meridian" / "workspaces" / str(workspace_id) / "workspace-summary.md"


def _load_workspace_runs(state: StateDB, workspace_id: WorkspaceId) -> list[sqlite3.Row]:
    conn = sqlite3.connect(state.paths.db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, status, model, started_at, finished_at, total_cost_usd, report_path
            FROM runs
            WHERE workspace_id = ?
            ORDER BY started_at DESC
            """,
            (str(workspace_id),),
        ).fetchall()
    finally:
        conn.close()
    return list(rows)


def _render_summary_markdown(
    workspace: Workspace,
    *,
    runs: list[sqlite3.Row],
    pinned_files: tuple[str, ...],
) -> str:
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines: list[str] = [
        f"# Workspace Summary: {workspace.workspace_id}",
        "",
        f"- Generated: {timestamp}",
        f"- State: {workspace.state}",
        f"- Name: {workspace.name or '(unnamed)'}",
        f"- Total runs: {len(runs)}",
        "",
        "## Pinned Context",
    ]

    if pinned_files:
        lines.extend([f"- `{path}`" for path in pinned_files])
    else:
        lines.append("- None")

    lines.extend(["", "## Recent Runs"])
    if runs:
        for row in runs:
            report_path = cast("str | None", row["report_path"])
            report_text = report_path if report_path else "(no report)"
            lines.append(
                "- "
                f"{row['id']} | {row['status']} | {row['model']} | "
                f"started {row['started_at']} | report {report_text}"
            )
    else:
        lines.append("- No runs yet")

    lines.append("")
    return "\n".join(lines)


def generate_workspace_summary(
    *,
    state: StateDB,
    repo_root: Path,
    workspace_id: WorkspaceId,
) -> Path:
    """Generate workspace-summary.md and update DB pointer."""

    workspace = state.get_workspace(workspace_id)
    if workspace is None:
        raise ValueError(f"Workspace '{workspace_id}' not found")

    summary_path = workspace_summary_path(repo_root, workspace_id)

    # workspace-summary.md is always durable pinned context for resume.
    state.pin_file(workspace_id, summary_path.as_posix())
    pinned_paths = tuple(sorted(item.file_path for item in state.list_pinned_files(workspace_id)))

    markdown = _render_summary_markdown(
        workspace,
        runs=_load_workspace_runs(state, workspace_id),
        pinned_files=pinned_paths,
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(markdown, encoding="utf-8")

    rel_summary = summary_path.relative_to(repo_root).as_posix()
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = sqlite3.connect(state.paths.db_path)
    try:
        with conn:
            conn.execute(
                """
                UPDATE workspaces
                SET summary_path = ?, last_activity_at = ?
                WHERE id = ?
                """,
                (rel_summary, now, str(workspace_id)),
            )
    finally:
        conn.close()

    return summary_path


def collect_workspace_markdown_artifacts(
    *,
    state: StateDB,
    repo_root: Path,
    workspace_id: WorkspaceId,
) -> tuple[Path, ...]:
    """Collect committable markdown artifact paths for one workspace."""

    summary = generate_workspace_summary(
        state=state,
        repo_root=repo_root,
        workspace_id=workspace_id,
    )
    found: dict[str, Path] = {summary.as_posix(): summary}

    conn = sqlite3.connect(state.paths.db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT report_path
            FROM runs
            WHERE workspace_id = ? AND report_path IS NOT NULL
            ORDER BY started_at DESC
            """,
            (str(workspace_id),),
        ).fetchall()
    finally:
        conn.close()

    for row in rows:
        report_path = cast("str", row["report_path"])
        resolved = Path(report_path)
        absolute = resolved if resolved.is_absolute() else repo_root / resolved
        if absolute.suffix.lower() != ".md" or not absolute.is_file():
            continue
        found[absolute.as_posix()] = absolute

    for pinned in state.list_pinned_files(workspace_id):
        absolute = Path(pinned.file_path)
        if absolute.suffix.lower() != ".md" or not absolute.is_file():
            continue
        found[absolute.as_posix()] = absolute

    return tuple(found[key] for key in sorted(found))
