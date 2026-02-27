"""SQLite-backed state + protocol adapters."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from meridian.lib.domain import (
    ArtifactRecord,
    PinnedFile,
    Run,
    RunCreateParams,
    RunEdge,
    RunEnrichment,
    RunFilters,
    RunStatus,
    RunSummary,
    Span,
    WorkflowEvent,
    Workspace,
    WorkspaceCreateParams,
    WorkspaceFilters,
    WorkspaceState,
    WorkspaceSummary,
)
from meridian.lib.state.db import (
    DEFAULT_BUSY_TIMEOUT_MS,
    StatePaths,
    open_connection,
    resolve_run_log_dir,
    resolve_state_paths,
)
from meridian.lib.state.id_gen import next_run_id, next_workspace_id
from meridian.lib.state.jsonl import JSONRow, append_jsonl_row, index_lock, read_jsonl_rows
from meridian.lib.types import (
    ArtifactKey,
    HarnessId,
    ModelId,
    RunId,
    SpanId,
    TraceId,
    WorkflowEventId,
    WorkspaceId,
)


def _empty_string_map() -> dict[str, str]:
    return {}


_ALLOWED_WORKSPACE_TRANSITIONS: dict[WorkspaceState, frozenset[WorkspaceState]] = {
    "active": frozenset({"paused", "completed", "abandoned"}),
    "paused": frozenset({"active", "completed", "abandoned"}),
    "completed": frozenset(),
    "abandoned": frozenset(),
}


def _workspace_transition_allowed(current: WorkspaceState, new_state: WorkspaceState) -> bool:
    if current == new_state:
        return True
    return new_state in _ALLOWED_WORKSPACE_TRANSITIONS[current]


@dataclass(frozen=True, slots=True)
class RunStartRow:
    """Input payload for start-row writes."""

    run_id: RunId
    model: ModelId
    harness: HarnessId
    cwd: Path
    log_dir: Path
    session_id: str
    workspace_id: WorkspaceId | None = None
    agent: str | None = None
    skills: tuple[str, ...] = ()
    labels: dict[str, str] = field(default_factory=_empty_string_map)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class RunFinalizeRow:
    """Input payload for finalize writes."""

    exit_code: int
    duration_seconds: float
    finished_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    failure_reason: str | None = None
    output_log: Path | None = None
    report_path: Path | None = None
    harness_session_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_cost_usd: float | None = None
    files_touched_count: int | None = None


class StateDB:
    """State API used by execution and query layers."""

    def __init__(
        self,
        repo_root: Path,
        *,
        jsonl_dual_write: bool = True,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    ) -> None:
        self._repo_root = repo_root.resolve()
        self._paths = resolve_state_paths(self._repo_root)
        self._jsonl_dual_write = jsonl_dual_write
        self._busy_timeout_ms = busy_timeout_ms

        self._paths.index_dir.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        conn.close()

    @property
    def paths(self) -> StatePaths:
        return self._paths

    def _connect(self) -> sqlite3.Connection:
        return open_connection(self._paths.db_path, busy_timeout_ms=self._busy_timeout_ms)

    def _to_relative(self, path: Path | None) -> str | None:
        if path is None:
            return None

        resolved = path.expanduser()
        if not resolved.is_absolute():
            return resolved.as_posix()

        try:
            return resolved.relative_to(self._repo_root).as_posix()
        except ValueError:
            return str(Path("..") / resolved.name)

    def _to_absolute(self, rel_path: str | None) -> Path | None:
        if rel_path is None:
            return None
        rel = Path(rel_path)
        if rel.is_absolute():
            return rel
        return self._repo_root / rel

    def append_start_row(self, row: RunStartRow) -> None:
        start_json = self._start_row_to_json(row)
        local_id = str(row.run_id).split("/")[-1]

        with index_lock(self._paths.lock_path, exclusive=True):
            conn = self._connect()
            try:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO runs(
                            id,
                            workspace_id,
                            local_id,
                            model,
                            agent,
                            skills,
                            labels,
                            harness,
                            status,
                            started_at,
                            cwd,
                            log_dir,
                            harness_session_id
                        )
                        VALUES(?, ?, ?, ?, ?, ?, ?, ?, 'running', ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            status = excluded.status,
                            started_at = excluded.started_at,
                            model = excluded.model,
                            agent = excluded.agent,
                            skills = excluded.skills,
                            labels = excluded.labels,
                            harness = excluded.harness,
                            cwd = excluded.cwd,
                            log_dir = excluded.log_dir,
                            harness_session_id = excluded.harness_session_id
                        """,
                        (
                            str(row.run_id),
                            str(row.workspace_id) if row.workspace_id is not None else None,
                            local_id,
                            str(row.model),
                            row.agent,
                            json.dumps(list(row.skills), sort_keys=True),
                            json.dumps(row.labels, sort_keys=True),
                            str(row.harness),
                            _as_utc_iso(row.started_at),
                            self._to_relative(row.cwd),
                            self._to_relative(row.log_dir),
                            row.session_id,
                        ),
                    )
                    if self._jsonl_dual_write:
                        append_jsonl_row(self._paths.jsonl_path, start_json)
            finally:
                conn.close()

    def append_finalize_row(self, run_id: RunId, row: RunFinalizeRow) -> None:
        status = "succeeded" if row.exit_code == 0 else "failed"
        failure_reason = row.failure_reason or _failure_reason_for_exit_code(row.exit_code)
        finalize_json = self._finalize_row_to_json(run_id, row, status, failure_reason)

        with index_lock(self._paths.lock_path, exclusive=True):
            conn = self._connect()
            try:
                with conn:
                    previous = conn.execute(
                        """
                        SELECT workspace_id, input_tokens, output_tokens, total_cost_usd
                        FROM runs
                        WHERE id = ?
                        """,
                        (str(run_id),),
                    ).fetchone()
                    if previous is None:
                        raise KeyError(f"Unknown run ID: {run_id}")

                    previous_input = int(previous["input_tokens"] or 0)
                    previous_output = int(previous["output_tokens"] or 0)
                    previous_cost = float(previous["total_cost_usd"] or 0.0)

                    final_input = (
                        int(row.input_tokens)
                        if row.input_tokens is not None
                        else previous_input
                    )
                    final_output = (
                        int(row.output_tokens) if row.output_tokens is not None else previous_output
                    )
                    final_cost = (
                        float(row.total_cost_usd)
                        if row.total_cost_usd is not None
                        else previous_cost
                    )

                    delta_input = final_input - previous_input
                    delta_output = final_output - previous_output
                    delta_cost = final_cost - previous_cost

                    result = conn.execute(
                        """
                        UPDATE runs
                        SET status = ?,
                            finished_at = ?,
                            duration_secs = ?,
                            exit_code = ?,
                            failure_reason = ?,
                            output_log = ?,
                            report_path = ?,
                            harness_session_id = COALESCE(?, harness_session_id),
                            input_tokens = COALESCE(?, input_tokens),
                            output_tokens = COALESCE(?, output_tokens),
                            total_cost_usd = COALESCE(?, total_cost_usd),
                            files_touched_count = COALESCE(?, files_touched_count)
                        WHERE id = ?
                        """,
                        (
                            status,
                            _as_utc_iso(row.finished_at),
                            row.duration_seconds,
                            row.exit_code,
                            failure_reason,
                            self._to_relative(row.output_log),
                            self._to_relative(row.report_path),
                            row.harness_session_id,
                            row.input_tokens,
                            row.output_tokens,
                            row.total_cost_usd,
                            row.files_touched_count,
                            str(run_id),
                        ),
                    )
                    _ = result

                    workspace_value = cast("str | None", previous["workspace_id"])
                    if workspace_value is not None and (
                        delta_input != 0 or delta_output != 0 or delta_cost != 0.0
                    ):
                        conn.execute(
                            """
                            UPDATE workspaces
                            SET total_input_tokens = MAX(total_input_tokens + ?, 0),
                                total_output_tokens = MAX(total_output_tokens + ?, 0),
                                total_cost_usd = MAX(total_cost_usd + ?, 0.0),
                                last_activity_at = ?
                            WHERE id = ?
                            """,
                            (
                                delta_input,
                                delta_output,
                                delta_cost,
                                _as_utc_iso(row.finished_at),
                                workspace_value,
                            ),
                        )

                    if self._jsonl_dual_write:
                        append_jsonl_row(self._paths.jsonl_path, finalize_json)
            finally:
                conn.close()

    def create_run(self, params: RunCreateParams) -> Run:
        conn = self._connect()
        try:
            with conn:
                generated = next_run_id(conn, params.workspace_id)
                started = datetime.now(UTC)
                run_dir = resolve_run_log_dir(
                    self._repo_root,
                    generated.full_id,
                    params.workspace_id,
                )
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
                        log_dir,
                        prompt
                    )
                    VALUES(?, ?, ?, ?, 'unknown', 'queued', ?, ?, ?)
                    """,
                    (
                        str(generated.full_id),
                        str(params.workspace_id) if params.workspace_id is not None else None,
                        str(generated.local_id),
                        str(params.model),
                        _as_utc_iso(started),
                        self._to_relative(run_dir),
                        params.prompt,
                    ),
                )
                if params.workspace_id is not None:
                    conn.execute(
                        """
                        UPDATE workspaces
                        SET total_runs = total_runs + 1,
                            last_activity_at = ?
                        WHERE id = ?
                        """,
                        (_as_utc_iso(started), str(params.workspace_id)),
                    )
        finally:
            conn.close()

        return Run(
            run_id=generated.full_id,
            prompt=params.prompt,
            model=params.model,
            status="queued",
            created_at=started,
            workspace_id=params.workspace_id,
        )

    def get_run(self, run_id: RunId) -> Run | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT id, prompt, model, status, started_at, workspace_id
                FROM runs
                WHERE id = ?
                """,
                (str(run_id),),
            ).fetchone()
        finally:
            conn.close()

        if row is None:
            return None

        workspace_value = cast("str | None", row["workspace_id"])
        return Run(
            run_id=RunId(str(row["id"])),
            prompt=str(row["prompt"] or ""),
            model=ModelId(str(row["model"])),
            status=cast("RunStatus", str(row["status"])),
            created_at=_parse_utc_timestamp(str(row["started_at"])),
            workspace_id=WorkspaceId(workspace_value) if workspace_value else None,
        )

    def list_runs(self, filters: RunFilters) -> list[RunSummary]:
        where: list[str] = []
        params: list[str] = []

        if filters.workspace_id is not None:
            where.append("workspace_id = ?")
            params.append(str(filters.workspace_id))
        if filters.status is not None:
            where.append("status = ?")
            params.append(filters.status)

        query = "SELECT id, status, model, workspace_id FROM runs"
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY started_at DESC"

        conn = self._connect()
        try:
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()

        summaries: list[RunSummary] = []
        for row in rows:
            workspace_value = cast("str | None", row["workspace_id"])
            summaries.append(
                RunSummary(
                    run_id=RunId(str(row["id"])),
                    status=cast("RunStatus", str(row["status"])),
                    model=ModelId(str(row["model"])),
                    workspace_id=WorkspaceId(workspace_value) if workspace_value else None,
                )
            )
        return summaries

    def update_run_status(self, run_id: RunId, status: RunStatus) -> None:
        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    "UPDATE runs SET status = ? WHERE id = ?",
                    (status, str(run_id)),
                )
        finally:
            conn.close()

    def enrich_run(self, run_id: RunId, enrichment: RunEnrichment) -> None:
        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    """
                    UPDATE runs
                    SET input_tokens = ?,
                        output_tokens = ?,
                        total_cost_usd = ?,
                        report_path = COALESCE(?, report_path)
                    WHERE id = ?
                    """,
                    (
                        enrichment.usage.input_tokens,
                        enrichment.usage.output_tokens,
                        enrichment.usage.total_cost_usd,
                        self._to_relative(enrichment.report_path),
                        str(run_id),
                    ),
                )
        finally:
            conn.close()

    def create_workspace(self, params: WorkspaceCreateParams) -> Workspace:
        conn = self._connect()
        try:
            with conn:
                workspace_id = next_workspace_id(conn)
                now = datetime.now(UTC)
                conn.execute(
                    """
                    INSERT INTO workspaces(
                        id,
                        name,
                        status,
                        started_at,
                        last_activity_at
                    )
                    VALUES(?, ?, 'active', ?, ?)
                    """,
                    (str(workspace_id), params.name, _as_utc_iso(now), _as_utc_iso(now)),
                )
        finally:
            conn.close()

        return Workspace(
            workspace_id=workspace_id,
            state="active",
            created_at=now,
            name=params.name,
        )

    def get_workspace(self, workspace_id: WorkspaceId) -> Workspace | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT id, status, started_at, name FROM workspaces WHERE id = ?",
                (str(workspace_id),),
            ).fetchone()
        finally:
            conn.close()

        if row is None:
            return None

        return Workspace(
            workspace_id=WorkspaceId(str(row["id"])),
            state=cast("WorkspaceState", str(row["status"])),
            created_at=_parse_utc_timestamp(str(row["started_at"])),
            name=cast("str | None", row["name"]),
        )

    def list_workspaces(self, filters: WorkspaceFilters) -> list[WorkspaceSummary]:
        query = "SELECT id, status, name FROM workspaces"
        params: list[str] = []
        if filters.state is not None:
            query += " WHERE status = ?"
            params.append(filters.state)
        query += " ORDER BY started_at DESC"

        conn = self._connect()
        try:
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()

        return [
            WorkspaceSummary(
                workspace_id=WorkspaceId(str(row["id"])),
                state=cast("WorkspaceState", str(row["status"])),
                name=cast("str | None", row["name"]),
            )
            for row in rows
        ]

    def transition_workspace(self, workspace_id: WorkspaceId, new_state: WorkspaceState) -> None:
        conn = self._connect()
        try:
            with conn:
                row = conn.execute(
                    "SELECT status FROM workspaces WHERE id = ?",
                    (str(workspace_id),),
                ).fetchone()
                if row is None:
                    raise KeyError(f"Unknown workspace ID: {workspace_id}")

                current_state = cast("WorkspaceState", str(row["status"]))
                if not _workspace_transition_allowed(current_state, new_state):
                    raise ValueError(
                        "Invalid workspace transition "
                        f"'{workspace_id}': {current_state} -> {new_state}."
                    )

                conn.execute(
                    """
                    UPDATE workspaces
                    SET status = ?,
                        last_activity_at = ?
                    WHERE id = ?
                    """,
                    (new_state, _as_utc_iso(datetime.now(UTC)), str(workspace_id)),
                )
        finally:
            conn.close()

    def pin_file(self, workspace_id: WorkspaceId, file_path: str) -> None:
        rel_path = self._to_relative(Path(file_path))
        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO pinned_files(workspace_id, file_path)
                    VALUES(?, ?)
                    ON CONFLICT(workspace_id, file_path) DO NOTHING
                    """,
                    (str(workspace_id), rel_path),
                )
        finally:
            conn.close()

    def unpin_file(self, workspace_id: WorkspaceId, file_path: str) -> None:
        rel_path = self._to_relative(Path(file_path))
        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    "DELETE FROM pinned_files WHERE workspace_id = ? AND file_path = ?",
                    (str(workspace_id), rel_path),
                )
        finally:
            conn.close()

    def list_pinned_files(self, workspace_id: WorkspaceId) -> list[PinnedFile]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT file_path FROM pinned_files WHERE workspace_id = ? ORDER BY file_path",
                (str(workspace_id),),
            ).fetchall()
        finally:
            conn.close()

        pinned: list[PinnedFile] = []
        for row in rows:
            abs_path = self._to_absolute(str(row["file_path"]))
            if abs_path is None:
                continue
            pinned.append(
                PinnedFile(
                    workspace_id=workspace_id,
                    file_path=abs_path.as_posix(),
                )
            )
        return pinned

    def append_workflow_event(
        self,
        *,
        workspace_id: WorkspaceId,
        event_type: str,
        payload: dict[str, Any],
        run_id: RunId | None = None,
        timestamp: datetime | None = None,
    ) -> WorkflowEvent:
        now = timestamp or datetime.now(UTC)
        conn = self._connect()
        try:
            with conn:
                row = conn.execute(
                    """
                    INSERT INTO workflow_events(
                        workspace_id, event_type, run_id, payload, timestamp
                    )
                    VALUES(?, ?, ?, ?, ?)
                    RETURNING id
                    """,
                    (
                        str(workspace_id),
                        event_type,
                        str(run_id) if run_id is not None else None,
                        json.dumps(payload, sort_keys=True),
                        _as_utc_iso(now),
                    ),
                ).fetchone()
        finally:
            conn.close()

        if row is None:
            raise RuntimeError("Failed to insert workflow event")

        return WorkflowEvent(
            event_id=WorkflowEventId(int(row[0])),
            workspace_id=workspace_id,
            event_type=event_type,
            payload=payload,
            run_id=run_id,
            timestamp=now,
        )

    def list_workflow_events(self, workspace_id: WorkspaceId) -> list[WorkflowEvent]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT id, event_type, payload, run_id, timestamp
                FROM workflow_events
                WHERE workspace_id = ?
                ORDER BY id ASC
                """,
                (str(workspace_id),),
            ).fetchall()
        finally:
            conn.close()

        events: list[WorkflowEvent] = []
        for row in rows:
            run_value = cast("str | None", row["run_id"])
            payload = json.loads(str(row["payload"]))
            if not isinstance(payload, dict):
                payload = {}
            events.append(
                WorkflowEvent(
                    event_id=WorkflowEventId(int(row["id"])),
                    workspace_id=workspace_id,
                    event_type=str(row["event_type"]),
                    payload=cast("dict[str, Any]", payload),
                    run_id=RunId(run_value) if run_value else None,
                    timestamp=_parse_utc_timestamp(str(row["timestamp"])),
                )
            )
        return events

    def add_span(self, span: Span) -> None:
        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO spans(
                        span_id,
                        trace_id,
                        parent_id,
                        name,
                        kind,
                        started_at,
                        ended_at,
                        status,
                        attributes
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(span.span_id),
                        str(span.trace_id),
                        str(span.parent_id) if span.parent_id is not None else None,
                        span.name,
                        span.kind,
                        _as_utc_iso(span.started_at),
                        _as_utc_iso(span.ended_at) if span.ended_at else None,
                        span.status,
                        json.dumps(dict(span.attributes), sort_keys=True),
                    ),
                )
        finally:
            conn.close()

    def finish_span(
        self,
        span_id: SpanId,
        *,
        ended_at: datetime | None = None,
        status: str = "ok",
        attributes: dict[str, Any] | None = None,
    ) -> None:
        ended = ended_at or datetime.now(UTC)
        attrs_json = json.dumps(attributes or {}, sort_keys=True)
        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    """
                    UPDATE spans
                    SET ended_at = ?,
                        status = ?,
                        attributes = ?
                    WHERE span_id = ?
                    """,
                    (_as_utc_iso(ended), status, attrs_json, str(span_id)),
                )
        finally:
            conn.close()

    def list_spans(self, trace_id: TraceId) -> list[Span]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT
                    span_id,
                    trace_id,
                    parent_id,
                    name,
                    kind,
                    started_at,
                    ended_at,
                    status,
                    attributes
                FROM spans
                WHERE trace_id = ?
                ORDER BY started_at ASC
                """,
                (str(trace_id),),
            ).fetchall()
        finally:
            conn.close()

        spans: list[Span] = []
        for row in rows:
            parent_value = cast("str | None", row["parent_id"])
            attrs_payload = json.loads(str(row["attributes"]))
            if not isinstance(attrs_payload, dict):
                attrs_payload = {}
            ended = cast("str | None", row["ended_at"])
            spans.append(
                Span(
                    span_id=SpanId(str(row["span_id"])),
                    trace_id=TraceId(str(row["trace_id"])),
                    parent_id=SpanId(parent_value) if parent_value else None,
                    name=str(row["name"]),
                    kind=str(row["kind"]),
                    started_at=_parse_utc_timestamp(str(row["started_at"])),
                    ended_at=_parse_utc_timestamp(ended) if ended else None,
                    status=str(row["status"]),
                    attributes=cast("dict[str, Any]", attrs_payload),
                )
            )
        return spans

    def add_run_edge(self, edge: RunEdge) -> None:
        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO run_edges(source_run_id, target_run_id, edge_type)
                    VALUES(?, ?, ?)
                    ON CONFLICT(source_run_id, target_run_id, edge_type) DO NOTHING
                    """,
                    (str(edge.source_run_id), str(edge.target_run_id), edge.edge_type),
                )
        finally:
            conn.close()

    def upsert_artifact(self, artifact: ArtifactRecord) -> None:
        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO artifacts(run_id, name, path, size)
                    VALUES(?, ?, ?, ?)
                    ON CONFLICT(run_id, name)
                    DO UPDATE SET path = excluded.path, size = excluded.size
                    """,
                    (
                        str(artifact.run_id),
                        str(artifact.key),
                        self._to_relative(artifact.path),
                        artifact.size,
                    ),
                )
        finally:
            conn.close()

    def list_artifact_records(self, run_id: RunId) -> list[ArtifactRecord]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT name, path, size FROM artifacts WHERE run_id = ? ORDER BY name",
                (str(run_id),),
            ).fetchall()
        finally:
            conn.close()

        records: list[ArtifactRecord] = []
        for row in rows:
            path = self._to_absolute(str(row["path"]))
            if path is None:
                continue
            size = cast("int | None", row["size"])
            records.append(
                ArtifactRecord(
                    run_id=run_id,
                    key=ArtifactKey(str(row["name"])),
                    path=path,
                    size=size,
                )
            )
        return records

    def read_jsonl_rows(self) -> list[JSONRow]:
        with index_lock(self._paths.lock_path, exclusive=False):
            return read_jsonl_rows(self._paths.jsonl_path)

    def _start_row_to_json(self, row: RunStartRow) -> JSONRow:
        payload: JSONRow = {
            "run_id": str(row.run_id),
            "status": "running",
            "created_at_utc": _as_utc_iso(row.started_at),
            "cwd": self._to_relative(row.cwd) or "",
            "session_id": row.session_id,
            "model": str(row.model),
            "harness": str(row.harness),
            "skills": list(row.skills),
            "labels": cast("dict[str, Any]", dict(row.labels)),
            "log_dir": self._to_relative(row.log_dir) or "",
        }
        if row.agent is not None:
            payload["agent"] = row.agent
        if row.workspace_id is not None:
            payload["workspace_id"] = str(row.workspace_id)
        return payload

    def _finalize_row_to_json(
        self,
        run_id: RunId,
        row: RunFinalizeRow,
        status: str,
        failure_reason: str | None,
    ) -> JSONRow:
        payload: JSONRow = {
            "run_id": str(run_id),
            "status": status,
            "finished_at_utc": _as_utc_iso(row.finished_at),
            "duration_seconds": row.duration_seconds,
            "exit_code": row.exit_code,
            "failure_reason": failure_reason,
            "output_log": self._to_relative(row.output_log),
            "report_path": self._to_relative(row.report_path),
            "harness_session_id": row.harness_session_id,
            "input_tokens": row.input_tokens,
            "output_tokens": row.output_tokens,
            "total_cost_usd": row.total_cost_usd,
            "files_touched_count": row.files_touched_count,
        }
        return payload


class SQLiteRunStoreSync:
    """Sync adapter for RunStoreSync protocol."""

    def __init__(self, state: StateDB) -> None:
        self._state = state

    def create(self, params: RunCreateParams) -> Run:
        return self._state.create_run(params)

    def get(self, run_id: RunId) -> Run | None:
        return self._state.get_run(run_id)

    def list(self, filters: RunFilters) -> list[RunSummary]:
        return self._state.list_runs(filters)

    def update_status(self, run_id: RunId, status: RunStatus) -> None:
        self._state.update_run_status(run_id, status)

    def enrich(self, run_id: RunId, enrichment: RunEnrichment) -> None:
        self._state.enrich_run(run_id, enrichment)


class SQLiteRunStore:
    """Async adapter for RunStore protocol backed by sync state access."""

    def __init__(self, sync_store: SQLiteRunStoreSync) -> None:
        self._sync_store = sync_store

    async def create(self, params: RunCreateParams) -> Run:
        return await asyncio.to_thread(self._sync_store.create, params)

    async def get(self, run_id: RunId) -> Run | None:
        return await asyncio.to_thread(self._sync_store.get, run_id)

    async def list(self, filters: RunFilters) -> list[RunSummary]:
        return await asyncio.to_thread(self._sync_store.list, filters)

    async def update_status(self, run_id: RunId, status: RunStatus) -> None:
        await asyncio.to_thread(self._sync_store.update_status, run_id, status)

    async def enrich(self, run_id: RunId, enrichment: RunEnrichment) -> None:
        await asyncio.to_thread(self._sync_store.enrich, run_id, enrichment)


class SQLiteWorkspaceStore:
    """Async adapter for WorkspaceStore protocol."""

    def __init__(self, state: StateDB) -> None:
        self._state = state

    async def create(self, params: WorkspaceCreateParams) -> Workspace:
        return await asyncio.to_thread(self._state.create_workspace, params)

    async def get(self, workspace_id: WorkspaceId) -> Workspace | None:
        return await asyncio.to_thread(self._state.get_workspace, workspace_id)

    async def list(self, filters: WorkspaceFilters) -> list[WorkspaceSummary]:
        return await asyncio.to_thread(self._state.list_workspaces, filters)

    async def transition(self, workspace_id: WorkspaceId, new_state: WorkspaceState) -> None:
        await asyncio.to_thread(self._state.transition_workspace, workspace_id, new_state)


class SQLiteContextStore:
    """Async adapter for ContextStore protocol."""

    def __init__(self, state: StateDB) -> None:
        self._state = state

    async def pin(self, workspace_id: WorkspaceId, file_path: str) -> None:
        await asyncio.to_thread(self._state.pin_file, workspace_id, file_path)

    async def unpin(self, workspace_id: WorkspaceId, file_path: str) -> None:
        await asyncio.to_thread(self._state.unpin_file, workspace_id, file_path)

    async def list_pinned(self, workspace_id: WorkspaceId) -> list[PinnedFile]:
        return await asyncio.to_thread(self._state.list_pinned_files, workspace_id)


def _as_utc_iso(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _failure_reason_for_exit_code(exit_code: int) -> str | None:
    if exit_code == 0:
        return None
    mapping = {
        1: "agent_error",
        2: "infra_error",
        3: "timeout",
        130: "interrupted",
        143: "interrupted",
    }
    return mapping.get(exit_code, "unknown")
