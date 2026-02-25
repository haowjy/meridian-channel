"""Diagnostics operations."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from meridian.lib.ops._runtime import build_runtime
from meridian.lib.ops.registry import OperationSpec, operation
from meridian.lib.state.db import open_connection
from meridian.lib.state.schema import REQUIRED_TABLES, list_tables
from meridian.lib.types import WorkspaceId
from meridian.lib.workspace.launch import workspace_lock_path

if TYPE_CHECKING:
    from meridian.lib.formatting import FormatContext


@dataclass(frozen=True, slots=True)
class DiagDoctorInput:
    repo_root: str | None = None


@dataclass(frozen=True, slots=True)
class DiagRepairInput:
    repo_root: str | None = None


@dataclass(frozen=True, slots=True)
class DiagDoctorOutput:
    ok: bool
    repo_root: str
    db_path: str
    schema_version: int
    run_count: int
    workspace_count: int
    agents_dir: str
    skills_dir: str
    warnings: tuple[str, ...] = ()

    def format_text(self, ctx: FormatContext | None = None) -> str:
        """Key-value health check output for text output mode."""
        from meridian.cli.format_helpers import kv_block

        status = "ok" if self.ok else "WARNINGS"
        pairs: list[tuple[str, str | None]] = [
            ("ok", status),
            ("repo_root", self.repo_root),
            ("db_path", self.db_path),
            ("schema_version", str(self.schema_version)),
            ("runs", str(self.run_count)),
            ("workspaces", str(self.workspace_count)),
            ("agents_dir", self.agents_dir),
            ("skills_dir", self.skills_dir),
        ]
        result = kv_block(pairs)
        for w in self.warnings:
            result += f"\nwarning: {w}"
        return result


@dataclass(frozen=True, slots=True)
class DiagRepairOutput:
    ok: bool
    repaired: tuple[str, ...]

    def format_text(self, ctx: FormatContext | None = None) -> str:
        """Repair summary for text output mode."""
        if not self.repaired:
            return "ok: no repairs needed"
        items = ", ".join(self.repaired)
        return f"ok: repaired {items}"


def diag_doctor_sync(payload: DiagDoctorInput) -> DiagDoctorOutput:
    runtime = build_runtime(payload.repo_root)
    conn = sqlite3.connect(runtime.state.paths.db_path)
    conn.row_factory = sqlite3.Row
    try:
        schema_row = conn.execute(
            "SELECT value FROM schema_info WHERE key = 'version'"
        ).fetchone()
        run_row = conn.execute("SELECT COUNT(*) AS count FROM runs").fetchone()
        workspace_row = conn.execute("SELECT COUNT(*) AS count FROM workspaces").fetchone()
    finally:
        conn.close()

    schema_version = int(schema_row["value"]) if schema_row is not None else 0
    run_count = int(run_row["count"]) if run_row is not None else 0
    workspace_count = int(workspace_row["count"]) if workspace_row is not None else 0
    agents_dir = runtime.repo_root / ".agents" / "agents"
    skills_dir = runtime.repo_root / ".agents" / "skills"
    warnings: list[str] = []
    if not skills_dir.is_dir():
        warnings.append("Missing .agents/skills directory.")
    if not agents_dir.is_dir():
        warnings.append("Missing .agents/agents directory.")

    return DiagDoctorOutput(
        ok=not warnings,
        repo_root=runtime.repo_root.as_posix(),
        db_path=runtime.state.paths.db_path.as_posix(),
        schema_version=schema_version,
        run_count=run_count,
        workspace_count=workspace_count,
        agents_dir=agents_dir.as_posix(),
        skills_dir=skills_dir.as_posix(),
        warnings=tuple(warnings),
    )


async def diag_doctor(payload: DiagDoctorInput) -> DiagDoctorOutput:
    return await asyncio.to_thread(diag_doctor_sync, payload)


def _jsonl_is_corrupt(path: Path) -> bool:
    if not path.exists():
        return True

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                return True
            if not isinstance(payload, dict):
                return True
    return False


def _rebuild_runs_jsonl(conn: sqlite3.Connection, path: Path) -> None:
    rows = conn.execute(
        """
        SELECT
            id,
            workspace_id,
            status,
            started_at,
            finished_at,
            duration_secs,
            exit_code,
            failure_reason,
            report_path,
            model,
            harness,
            total_cost_usd,
            input_tokens,
            output_tokens,
            files_touched_count
        FROM runs
        ORDER BY started_at ASC
        """
    ).fetchall()

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            payload: dict[str, object] = {
                "run_id": str(row["id"]),
                "status": str(row["status"]),
                "created_at_utc": str(row["started_at"]),
                "finished_at_utc": cast("str | None", row["finished_at"]),
                "duration_seconds": cast("float | None", row["duration_secs"]),
                "exit_code": cast("int | None", row["exit_code"]),
                "failure_reason": cast("str | None", row["failure_reason"]),
                "report_path": cast("str | None", row["report_path"]),
                "model": str(row["model"]),
                "harness": str(row["harness"]),
                "total_cost_usd": cast("float | None", row["total_cost_usd"]),
                "input_tokens": cast("int | None", row["input_tokens"]),
                "output_tokens": cast("int | None", row["output_tokens"]),
                "files_touched_count": cast("int | None", row["files_touched_count"]),
            }
            workspace_id = cast("str | None", row["workspace_id"])
            if workspace_id:
                payload["workspace_id"] = workspace_id

            handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _repair_workspace_locks(repo_root: Path) -> bool:
    lock_dir = repo_root / ".meridian" / "active-workspaces"
    if not lock_dir.exists():
        return False

    removed = False
    for lock_file in sorted(lock_dir.glob("*.lock")):
        if not lock_file.is_file():
            continue
        try:
            payload = json.loads(lock_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            lock_file.unlink(missing_ok=True)
            removed = True
            continue

        child_pid = payload.get("child_pid")
        if isinstance(child_pid, int) and child_pid > 0:
            proc_path = Path("/proc") / str(child_pid)
            if proc_path.exists():
                continue

        lock_file.unlink(missing_ok=True)
        removed = True

    return removed


def _repair_stuck_active_workspaces(conn: sqlite3.Connection, repo_root: Path) -> bool:
    rows = conn.execute("SELECT id FROM workspaces WHERE status = 'active'").fetchall()
    repaired = False

    with conn:
        for row in rows:
            workspace_id = WorkspaceId(str(row["id"]))
            if workspace_lock_path(repo_root, workspace_id).is_file():
                continue

            result = conn.execute(
                """
                UPDATE workspaces
                SET status = 'abandoned',
                    last_activity_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
                WHERE id = ? AND status = 'active'
                """,
                (str(workspace_id),),
            )
            repaired = repaired or result.rowcount > 0

    return repaired


def diag_repair_sync(payload: DiagRepairInput) -> DiagRepairOutput:
    runtime = build_runtime(payload.repo_root)
    repaired: list[str] = []

    existing_before: set[str]
    conn_before = sqlite3.connect(runtime.state.paths.db_path)
    try:
        existing_before = list_tables(conn_before)
    finally:
        conn_before.close()

    if _repair_workspace_locks(runtime.repo_root):
        repaired.append("workspace_locks")

    conn = open_connection(runtime.state.paths.db_path)
    try:
        existing_after = list_tables(conn)
        if REQUIRED_TABLES - existing_before and not (REQUIRED_TABLES - existing_after):
            repaired.append("schema_tables")

        if _jsonl_is_corrupt(runtime.state.paths.jsonl_path):
            _rebuild_runs_jsonl(conn, runtime.state.paths.jsonl_path)
            repaired.append("runs_jsonl")

        if _repair_stuck_active_workspaces(conn, runtime.repo_root):
            repaired.append("workspace_stuck_active")

        checkpoint = conn.execute("PRAGMA wal_checkpoint(FULL)").fetchone()
        if checkpoint is not None:
            repaired.append("wal_checkpoint")
    finally:
        conn.close()

    return DiagRepairOutput(ok=True, repaired=tuple(sorted(set(repaired))))


async def diag_repair(payload: DiagRepairInput) -> DiagRepairOutput:
    return await asyncio.to_thread(diag_repair_sync, payload)


operation(
    OperationSpec[DiagDoctorInput, DiagDoctorOutput](
        name="diag.doctor",
        handler=diag_doctor,
        sync_handler=diag_doctor_sync,
        input_type=DiagDoctorInput,
        output_type=DiagDoctorOutput,
        cli_group="diag",
        cli_name="doctor",
        mcp_name="diag_doctor",
        description="Run diagnostics checks.",
    )
)

operation(
    OperationSpec[DiagRepairInput, DiagRepairOutput](
        name="diag.repair",
        handler=diag_repair,
        sync_handler=diag_repair_sync,
        input_type=DiagRepairInput,
        output_type=DiagRepairOutput,
        cli_group="diag",
        cli_name="repair",
        mcp_name="diag_repair",
        description="Repair common state issues.",
    )
)
