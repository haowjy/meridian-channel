"""Migration operations for legacy JSONL and skill layout updates."""

from __future__ import annotations

import asyncio
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

from meridian.lib.ops._runtime import build_runtime
from meridian.lib.ops.registry import OperationSpec, operation
from meridian.lib.state.db import open_connection
from meridian.lib.state.jsonl import read_jsonl_rows

if TYPE_CHECKING:
    from meridian.lib.formatting import FormatContext

_WORKSPACE_COUNTER_KEY = "counter:workspace"
_GLOBAL_RUN_COUNTER_KEY = "counter:run:global"


@dataclass(frozen=True, slots=True)
class MigrateRunInput:
    repo_root: str | None = None
    jsonl_path: str | None = None
    apply_skill_migrations: bool = True


@dataclass(frozen=True, slots=True)
class MigrateRunOutput:
    ok: bool
    jsonl_path: str
    imported_runs: int
    updated_runs: int
    skipped_rows: int
    renamed_skill_dirs: tuple[str, ...]
    updated_reference_files: int

    def format_text(self, ctx: FormatContext | None = None) -> str:
        """Migration summary line for text output mode."""
        parts: list[str] = [
            f"imported={self.imported_runs}",
            f"updated={self.updated_runs}",
            f"skipped={self.skipped_rows}",
        ]
        if self.renamed_skill_dirs:
            parts.append(f"renamed={','.join(self.renamed_skill_dirs)}")
        if self.updated_reference_files:
            parts.append(f"ref_updates={self.updated_reference_files}")
        return "migrate.run  ok  " + "  ".join(parts)


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(stripped)
        except ValueError:
            return None
    return None


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if stripped.startswith("$"):
            stripped = stripped[1:]
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def _to_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _extract_run_id(row: dict[str, object]) -> str | None:
    for key in ("run_id", "id"):
        run_id = _to_text(row.get(key))
        if run_id:
            return run_id
    return None


def _extract_local_id(run_id: str) -> str:
    return run_id.split("/")[-1]


def _extract_workspace_id(row: dict[str, object], run_id: str) -> str | None:
    explicit = _to_text(row.get("workspace_id"))
    if explicit:
        return explicit
    if "/" in run_id:
        return run_id.split("/", 1)[0]
    return None


def _extract_started_at(row: dict[str, object]) -> str:
    return (
        _to_text(row.get("created_at_utc"))
        or _to_text(row.get("started_at"))
        or _to_text(row.get("started_at_utc"))
        or _now_iso()
    )


def _extract_log_dir(*, run_id: str, workspace_id: str | None, row: dict[str, object]) -> str:
    existing = _to_text(row.get("log_dir"))
    if existing is not None:
        return existing
    if workspace_id is None:
        return f".meridian/runs/{run_id}"
    return f".meridian/workspaces/{workspace_id}/runs/{_extract_local_id(run_id)}"


def _ensure_workspace_row(conn: sqlite3.Connection, workspace_id: str, started_at: str) -> None:
    conn.execute(
        """
        INSERT INTO workspaces(id, status, started_at, last_activity_at)
        VALUES(?, 'paused', ?, ?)
        ON CONFLICT(id) DO NOTHING
        """,
        (workspace_id, started_at, started_at),
    )


def _upsert_run_row(conn: sqlite3.Connection, row: dict[str, object]) -> bool:
    run_id = _extract_run_id(row)
    if run_id is None:
        return False

    workspace_id = _extract_workspace_id(row, run_id)
    started_at = _extract_started_at(row)
    if workspace_id is not None:
        _ensure_workspace_row(conn, workspace_id, started_at)

    conn.execute(
        """
        INSERT INTO runs(
            id,
            workspace_id,
            local_id,
            model,
            harness,
            status,
            started_at,
            finished_at,
            duration_secs,
            exit_code,
            failure_reason,
            report_path,
            log_dir,
            prompt,
            input_tokens,
            output_tokens,
            total_cost_usd,
            files_touched_count,
            output_log,
            harness_session_id
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            workspace_id = COALESCE(excluded.workspace_id, runs.workspace_id),
            local_id = COALESCE(excluded.local_id, runs.local_id),
            model = COALESCE(excluded.model, runs.model),
            harness = COALESCE(excluded.harness, runs.harness),
            status = COALESCE(excluded.status, runs.status),
            started_at = COALESCE(excluded.started_at, runs.started_at),
            finished_at = COALESCE(excluded.finished_at, runs.finished_at),
            duration_secs = COALESCE(excluded.duration_secs, runs.duration_secs),
            exit_code = COALESCE(excluded.exit_code, runs.exit_code),
            failure_reason = COALESCE(excluded.failure_reason, runs.failure_reason),
            report_path = COALESCE(excluded.report_path, runs.report_path),
            log_dir = COALESCE(excluded.log_dir, runs.log_dir),
            prompt = CASE
                WHEN excluded.prompt IS NOT NULL AND excluded.prompt != '' THEN excluded.prompt
                ELSE runs.prompt
            END,
            input_tokens = COALESCE(excluded.input_tokens, runs.input_tokens),
            output_tokens = COALESCE(excluded.output_tokens, runs.output_tokens),
            total_cost_usd = COALESCE(excluded.total_cost_usd, runs.total_cost_usd),
            files_touched_count = COALESCE(excluded.files_touched_count, runs.files_touched_count),
            output_log = COALESCE(excluded.output_log, runs.output_log),
            harness_session_id = COALESCE(excluded.harness_session_id, runs.harness_session_id)
        """,
        (
            run_id,
            workspace_id,
            _extract_local_id(run_id),
            _to_text(row.get("model")) or "unknown-model",
            _to_text(row.get("harness")) or "unknown",
            _to_text(row.get("status")) or "queued",
            started_at,
            _to_text(row.get("finished_at_utc")) or _to_text(row.get("finished_at")),
            _to_float(row.get("duration_seconds")) or _to_float(row.get("duration_secs")),
            _to_int(row.get("exit_code")),
            _to_text(row.get("failure_reason")),
            _to_text(row.get("report_path")),
            _extract_log_dir(run_id=run_id, workspace_id=workspace_id, row=row),
            _to_text(row.get("prompt")) or "",
            _to_int(row.get("input_tokens")),
            _to_int(row.get("output_tokens")),
            _to_float(row.get("total_cost_usd")),
            _to_int(row.get("files_touched_count")),
            _to_text(row.get("output_log")),
            _to_text(row.get("harness_session_id")) or _to_text(row.get("session_id")),
        ),
    )
    return True


def _set_counter_floor(conn: sqlite3.Connection, key: str, counter: int) -> None:
    conn.execute(
        """
        INSERT INTO schema_info(key, value)
        VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = CASE
                WHEN CAST(schema_info.value AS INTEGER) < CAST(excluded.value AS INTEGER)
                THEN excluded.value
                ELSE schema_info.value
            END
        """,
        (key, str(counter)),
    )


def _extract_numeric_id(prefix: str, value: str) -> int | None:
    match = re.fullmatch(rf"{re.escape(prefix)}([0-9]+)", value)
    if match is None:
        return None
    return int(match.group(1))


def _reconcile_workspace_rollups(conn: sqlite3.Connection) -> None:
    rows = conn.execute("SELECT id FROM workspaces").fetchall()
    for row in rows:
        workspace_id = str(row[0])
        counters = conn.execute(
            """
            SELECT
                COUNT(*) AS total_runs,
                COALESCE(SUM(total_cost_usd), 0.0) AS total_cost_usd,
                COALESCE(SUM(input_tokens), 0) AS total_input_tokens,
                COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
                COALESCE(MAX(CAST(SUBSTR(local_id, 2) AS INTEGER)), 0) AS run_counter,
                COALESCE(MAX(COALESCE(finished_at, started_at)), ?) AS last_activity
            FROM runs
            WHERE workspace_id = ?
            """,
            (_now_iso(), workspace_id),
        ).fetchone()
        if counters is None:
            continue

        conn.execute(
            """
            UPDATE workspaces
            SET total_runs = ?,
                total_cost_usd = ?,
                total_input_tokens = ?,
                total_output_tokens = ?,
                run_counter = ?,
                last_activity_at = ?
            WHERE id = ?
            """,
            (
                int(counters["total_runs"]),
                float(counters["total_cost_usd"]),
                int(counters["total_input_tokens"]),
                int(counters["total_output_tokens"]),
                int(counters["run_counter"]),
                str(counters["last_activity"]),
                workspace_id,
            ),
        )


def _sync_counters(conn: sqlite3.Connection) -> None:
    run_rows = conn.execute("SELECT id FROM runs WHERE workspace_id IS NULL").fetchall()
    max_global_run = 0
    for row in run_rows:
        parsed = _extract_numeric_id("r", str(row[0]))
        if parsed is not None:
            max_global_run = max(max_global_run, parsed)

    workspace_rows = conn.execute("SELECT id FROM workspaces").fetchall()
    max_workspace = 0
    for row in workspace_rows:
        parsed = _extract_numeric_id("w", str(row[0]))
        if parsed is not None:
            max_workspace = max(max_workspace, parsed)

    _set_counter_floor(conn, _GLOBAL_RUN_COUNTER_KEY, max_global_run)
    _set_counter_floor(conn, _WORKSPACE_COUNTER_KEY, max_workspace)


def _rename_skill_directories(repo_root: Path) -> tuple[str, ...]:
    skills_root = repo_root / ".agents" / "skills"
    mapping = {
        "plan-slicing": "plan-slice",
        "reviewing": "review",
        "researching": "research",
    }
    renamed: list[str] = []
    for old_name, new_name in mapping.items():
        old_path = skills_root / old_name
        new_path = skills_root / new_name
        if not old_path.exists() or new_path.exists():
            continue
        old_path.rename(new_path)
        renamed.append(f"{old_name}->{new_name}")
    return tuple(renamed)


def _update_skill_and_agent_references(repo_root: Path) -> int:
    replacements = (
        ("run-agent/scripts/run-agent.sh", "meridian run"),
        ("./run-agent.sh", "meridian run"),
        ("run-agent.sh", "meridian run"),
        ("plan-slicing", "plan-slice"),
        ("reviewing", "review"),
        ("researching", "research"),
    )

    changed_count = 0
    markdown_files: list[Path] = []
    skills_root = repo_root / ".agents" / "skills"
    agents_root = repo_root / ".agents" / "agents"
    if skills_root.is_dir():
        markdown_files.extend(path for path in skills_root.rglob("SKILL.md") if path.is_file())
    if agents_root.is_dir():
        markdown_files.extend(path for path in agents_root.glob("*.md") if path.is_file())

    for path in markdown_files:
        original = path.read_text(encoding="utf-8")
        updated = original
        for before, after in replacements:
            updated = updated.replace(before, after)
        if updated == original:
            continue
        path.write_text(updated, encoding="utf-8")
        changed_count += 1

    return changed_count


def migrate_run_sync(payload: MigrateRunInput) -> MigrateRunOutput:
    runtime = build_runtime(payload.repo_root)
    jsonl_path = (
        Path(payload.jsonl_path).expanduser().resolve()
        if payload.jsonl_path is not None and payload.jsonl_path.strip()
        else runtime.state.paths.jsonl_path
    )

    rows = read_jsonl_rows(jsonl_path)
    db = open_connection(runtime.state.paths.db_path)
    try:
        existing_ids = {
            str(row[0])
            for row in db.execute("SELECT id FROM runs").fetchall()
        }

        imported_runs = 0
        updated_runs = 0
        skipped_rows = 0
        inserted_during_migration: set[str] = set()

        with db:
            for row in rows:
                parsed = cast("dict[str, object]", row)
                run_id = _extract_run_id(parsed)
                if run_id is None:
                    skipped_rows += 1
                    continue

                if not _upsert_run_row(db, parsed):
                    skipped_rows += 1
                    continue

                if run_id in existing_ids or run_id in inserted_during_migration:
                    updated_runs += 1
                else:
                    imported_runs += 1
                    inserted_during_migration.add(run_id)

            _reconcile_workspace_rollups(db)
            _sync_counters(db)
    finally:
        db.close()

    renamed: tuple[str, ...] = ()
    updated_references = 0
    if payload.apply_skill_migrations:
        renamed = _rename_skill_directories(runtime.repo_root)
        updated_references = _update_skill_and_agent_references(runtime.repo_root)

    return MigrateRunOutput(
        ok=True,
        jsonl_path=jsonl_path.as_posix(),
        imported_runs=imported_runs,
        updated_runs=updated_runs,
        skipped_rows=skipped_rows,
        renamed_skill_dirs=renamed,
        updated_reference_files=updated_references,
    )


async def migrate_run(payload: MigrateRunInput) -> MigrateRunOutput:
    return await asyncio.to_thread(migrate_run_sync, payload)


operation(
    OperationSpec[MigrateRunInput, MigrateRunOutput](
        name="migrate.run",
        handler=migrate_run,
        sync_handler=migrate_run_sync,
        input_type=MigrateRunInput,
        output_type=MigrateRunOutput,
        cli_group="migrate",
        cli_name="run",
        mcp_name="migrate_run",
        description="Import legacy runs.jsonl into SQLite and apply skill migrations.",
        cli_only=True,
    )
)
