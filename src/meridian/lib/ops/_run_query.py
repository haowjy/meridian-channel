"""Run state query and row-shaping helpers."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import cast

from meridian.lib.state.db import resolve_state_paths
from meridian.lib.types import RunId

from ._run_models import RunDetailOutput, RunListFilters


def _read_run_row(repo_root: Path, run_id: str) -> sqlite3.Row | None:
    db_path = resolve_state_paths(repo_root).db_path
    if not db_path.is_file():
        return None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            """
            SELECT
                id,
                workspace_id,
                prompt,
                model,
                harness,
                status,
                started_at,
                finished_at,
                duration_secs,
                exit_code,
                failure_reason,
                input_tokens,
                output_tokens,
                total_cost_usd,
                report_path,
                skills,
                files_touched_count
            FROM runs
            WHERE id = ?
            """,
            (run_id,),
        ).fetchone()
    finally:
        conn.close()


def _read_report_text(repo_root: Path, report_path: str | None) -> str | None:
    if report_path is None:
        return None
    path = Path(report_path)
    resolved = path if path.is_absolute() else repo_root / path
    if not resolved.exists() or not resolved.is_file():
        return None
    return resolved.read_text(encoding="utf-8", errors="ignore").strip() or None


def _read_files_touched(repo_root: Path, run_id: str) -> tuple[str, ...]:
    from meridian.lib.extract.files_touched import extract_files_touched
    from meridian.lib.state.artifact_store import LocalStore

    artifacts = LocalStore(resolve_state_paths(repo_root).artifacts_dir)
    return extract_files_touched(artifacts, RunId(run_id))


def _detail_from_row(
    *,
    repo_root: Path,
    row: sqlite3.Row,
    include_report: bool,
    include_files: bool,
) -> RunDetailOutput:
    report_path = cast("str | None", row["report_path"])
    report_text = _read_report_text(repo_root, report_path)
    report_summary = report_text[:500] if report_text else None

    files_touched: tuple[str, ...] | None = None
    if include_files:
        files_touched = _read_files_touched(repo_root, str(row["id"]))

    skills_text = str(row["skills"] or "[]")
    parsed_skills_payload: object
    try:
        parsed_skills_payload = json.loads(skills_text)
    except json.JSONDecodeError:
        parsed_skills_payload = []
    parsed_skills = cast(
        "list[object]",
        parsed_skills_payload if isinstance(parsed_skills_payload, list) else [],
    )
    skills = tuple(str(item) for item in parsed_skills if isinstance(item, str))

    return RunDetailOutput(
        run_id=str(row["id"]),
        status=str(row["status"]),
        model=str(row["model"]),
        harness=str(row["harness"]),
        workspace_id=cast("str | None", row["workspace_id"]),
        started_at=str(row["started_at"]),
        finished_at=cast("str | None", row["finished_at"]),
        duration_secs=cast("float | None", row["duration_secs"]),
        exit_code=cast("int | None", row["exit_code"]),
        failure_reason=cast("str | None", row["failure_reason"]),
        input_tokens=cast("int | None", row["input_tokens"]),
        output_tokens=cast("int | None", row["output_tokens"]),
        cost_usd=cast("float | None", row["total_cost_usd"]),
        report_path=report_path,
        report_summary=report_summary,
        report=report_text if include_report else None,
        files_touched=files_touched,
        skills=skills,
    )


def _build_run_list_query(filters: RunListFilters) -> tuple[str, tuple[object, ...]]:
    where: list[str] = []
    params: list[object] = []

    if filters.workspace is not None:
        where.append("workspace_id = ?")
        params.append(filters.workspace)
    if filters.no_workspace:
        where.append("workspace_id IS NULL")
    if filters.status is not None:
        where.append("status = ?")
        params.append(filters.status)
    if filters.failed:
        where.append("status = ?")
        params.append("failed")
    if filters.model is not None:
        where.append("model = ?")
        params.append(filters.model)

    query = "SELECT id, status, model, workspace_id, duration_secs, total_cost_usd FROM runs"
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY started_at DESC LIMIT ?"
    params.append(filters.limit if filters.limit > 0 else 20)
    return query, tuple(params)
