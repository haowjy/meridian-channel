"""Shared helpers across harness adapters."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import cast

from meridian.lib.domain import TokenUsage
from meridian.lib.harness.adapter import ArtifactStore, StreamEvent
from meridian.lib.types import ArtifactKey, RunId


def parse_json_stream_event(line: str) -> StreamEvent | None:
    stripped = line.strip()
    if not stripped:
        return None
    try:
        payload_obj = json.loads(stripped)
    except json.JSONDecodeError:
        return StreamEvent(event_type="line", raw_line=line, text=stripped)

    if not isinstance(payload_obj, dict):
        return StreamEvent(event_type="line", raw_line=line, text=stripped)

    payload = cast("dict[str, object]", payload_obj)
    event_type = str(payload.get("type") or payload.get("event") or "line")
    text = payload.get("text") or payload.get("message")
    if text is not None:
        return StreamEvent(event_type=event_type, raw_line=line, text=str(text))
    return StreamEvent(event_type=event_type, raw_line=line, text=None)


def _read_json_artifact(
    artifacts: ArtifactStore, run_id: RunId, filename: str
) -> dict[str, object] | None:
    artifact_key = ArtifactKey(f"{run_id}/{filename}")
    if not artifacts.exists(artifact_key):
        return None
    raw = artifacts.get(artifact_key)
    try:
        payload_obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if isinstance(payload_obj, dict):
        return cast("dict[str, object]", payload_obj)
    return None


@dataclass(frozen=True, slots=True)
class _UsageCandidate:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_cost_usd: float | None = None


TOKEN_KEY_PAIRS: tuple[tuple[str, str], ...] = (
    ("input_tokens", "output_tokens"),
    ("input", "output"),
    ("prompt_tokens", "completion_tokens"),
    ("prompt_token_count", "completion_token_count"),
    ("inputTokenCount", "outputTokenCount"),
)
COST_KEYS: tuple[str, ...] = (
    "total_cost_usd",
    "cost_usd",
    "cost",
    "total_cost",
    "totalCostUsd",
)


def _coerce_optional_int(value: object) -> int | None:
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


def _coerce_optional_float(value: object) -> float | None:
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


def _iter_dicts(value: object) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    if isinstance(value, dict):
        payload = cast("dict[str, object]", value)
        found.append(payload)
        for nested in payload.values():
            found.extend(_iter_dicts(nested))
    elif isinstance(value, list):
        for item in cast("list[object]", value):
            found.extend(_iter_dicts(item))
    return found


def _extract_cost(payload: dict[str, object]) -> float | None:
    for key in COST_KEYS:
        value = _coerce_optional_float(payload.get(key))
        if value is not None:
            return value
    return None


def _candidate_from_payload(payload: dict[str, object]) -> _UsageCandidate:
    for input_key, output_key in TOKEN_KEY_PAIRS:
        if input_key not in payload and output_key not in payload:
            continue
        input_tokens = _coerce_optional_int(payload.get(input_key))
        output_tokens = _coerce_optional_int(payload.get(output_key))
        cost = _extract_cost(payload)
        return _UsageCandidate(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_cost_usd=cost,
        )

    return _UsageCandidate(total_cost_usd=_extract_cost(payload))


def _candidate_token_score(candidate: _UsageCandidate) -> int:
    score = 0
    if candidate.input_tokens is not None:
        score += 1
    if candidate.output_tokens is not None:
        score += 1
    return score


def _iter_json_lines_artifact(
    artifacts: ArtifactStore, run_id: RunId, filename: str
) -> list[dict[str, object]]:
    artifact_key = ArtifactKey(f"{run_id}/{filename}")
    if not artifacts.exists(artifact_key):
        return []

    raw = artifacts.get(artifact_key)
    decoded = raw.decode("utf-8", errors="ignore")
    payloads: list[dict[str, object]] = []
    for line in decoded.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload_obj = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload_obj, dict):
            payloads.append(cast("dict[str, object]", payload_obj))
    return payloads


def extract_usage_from_artifacts(artifacts: ArtifactStore, run_id: RunId) -> TokenUsage:
    candidates: list[_UsageCandidate] = []

    for filename in ("tokens.json", "usage.json"):
        payload = _read_json_artifact(artifacts, run_id, filename)
        if payload is None:
            continue
        for nested in _iter_dicts(payload):
            candidates.append(_candidate_from_payload(nested))

    for payload in _iter_json_lines_artifact(artifacts, run_id, "output.jsonl"):
        for nested in _iter_dicts(payload):
            candidates.append(_candidate_from_payload(nested))

    if not candidates:
        return TokenUsage()

    best_tokens = max(candidates, key=_candidate_token_score)
    best_cost = next(
        (
            candidate.total_cost_usd
            for candidate in candidates
            if candidate.total_cost_usd is not None
        ),
        None,
    )

    if _candidate_token_score(best_tokens) == 0 and best_cost is None:
        return TokenUsage()

    return TokenUsage(
        input_tokens=best_tokens.input_tokens or 0,
        output_tokens=best_tokens.output_tokens or 0,
        total_cost_usd=best_cost,
    )


def extract_session_id_from_artifacts(artifacts: ArtifactStore, run_id: RunId) -> str | None:
    key = ArtifactKey(f"{run_id}/session_id.txt")
    if not artifacts.exists(key):
        for payload in _iter_json_lines_artifact(artifacts, run_id, "output.jsonl"):
            for nested in _iter_dicts(payload):
                for key_name in ("session_id", "sessionId"):
                    value = nested.get(key_name)
                    if not isinstance(value, str):
                        continue
                    stripped = value.strip()
                    if stripped:
                        return stripped
        return None

    raw = artifacts.get(key)
    session_id = raw.decode("utf-8", errors="ignore").strip()
    return session_id or None
