"""Shared runner helper functions used by subprocess and streaming paths."""

from __future__ import annotations

import json
from pathlib import Path

import structlog

from meridian.lib.core.domain import Spawn
from meridian.lib.core.types import SpawnId
from meridian.lib.launch.constants import OUTPUT_FILENAME, STDERR_FILENAME
from meridian.lib.safety.budget import BudgetBreach
from meridian.lib.safety.guardrails import GuardrailFailure
from meridian.lib.safety.redaction import SecretSpec, redact_secret_bytes
from meridian.lib.state import spawn_store
from meridian.lib.state.artifact_store import ArtifactStore, make_artifact_key
from meridian.lib.state.atomic import atomic_write_bytes

logger = structlog.get_logger(__name__)


def spawn_kind(state_root: Path, spawn_id: SpawnId) -> str:
    row = spawn_store.get_spawn(state_root, spawn_id)
    if row is None:
        return "child"
    normalized = row.kind.strip().lower()
    if normalized in {"primary", "child"}:
        return normalized
    return "child"


def append_budget_exceeded_event(*, run: Spawn, breach: BudgetBreach) -> None:
    logger.warning(
        "Spawn budget exceeded.",
        spawn_id=str(run.spawn_id),
        scope=breach.scope,
        observed_usd=breach.observed_usd,
        limit_usd=breach.limit_usd,
    )


def guardrail_failure_text(failures: tuple[GuardrailFailure, ...]) -> str:
    lines = ["Guardrail validation failed:"]
    for failure in failures:
        lines.append(
            f"- {failure.script} (exit {failure.exit_code})"
            + (f": {failure.stderr}" if failure.stderr else "")
        )
    return "\n".join(lines)


def append_text_to_stderr_artifact(
    *,
    artifacts: ArtifactStore,
    spawn_id: SpawnId,
    text: str,
    secrets: tuple[SecretSpec, ...],
) -> None:
    key = make_artifact_key(spawn_id, STDERR_FILENAME)
    existing = artifacts.get(key).decode("utf-8", errors="ignore") if artifacts.exists(key) else ""
    prefix = "\n" if existing and not existing.endswith("\n") else ""
    combined = f"{existing}{prefix}{text}\n"
    artifacts.put(key, redact_secret_bytes(combined.encode("utf-8"), secrets))


def artifact_is_zero_bytes(
    *,
    artifacts: ArtifactStore,
    spawn_id: SpawnId,
    filename: str,
) -> bool:
    key = make_artifact_key(spawn_id, filename)
    if not artifacts.exists(key):
        return True
    return len(artifacts.get(key)) == 0


def write_structured_failure_artifact(
    *,
    artifacts: ArtifactStore,
    spawn_id: SpawnId,
    output_log_path: Path,
    exit_code: int,
    failure_reason: str | None,
    timed_out: bool,
) -> None:
    payload = {
        "error_code": "harness_empty_output",
        "failure_reason": failure_reason or "empty_output",
        "exit_code": exit_code,
        "timed_out": timed_out,
    }
    encoded = f"{json.dumps(payload, sort_keys=True)}\n".encode()
    artifacts.put(make_artifact_key(spawn_id, OUTPUT_FILENAME), encoded)
    atomic_write_bytes(output_log_path, encoded)


__all__ = [
    "append_budget_exceeded_event",
    "append_text_to_stderr_artifact",
    "artifact_is_zero_bytes",
    "guardrail_failure_text",
    "spawn_kind",
    "write_structured_failure_artifact",
]
