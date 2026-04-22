"""Unit tests for extension observability helpers."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from meridian.lib.extensions.observability import (
    ExtensionInvocationSummary,
    InvocationTimer,
    ObservabilityWriter,
    RedactionPipeline,
)


def test_redaction_removes_secret_keys_case_insensitively() -> None:
    payload = {
        "name": "ok",
        "TOKEN": "abc",
        "Api_Key": "xyz",
        "password": "hidden",
    }

    redacted = RedactionPipeline.redact(payload)

    assert redacted == {"name": "ok"}


def test_redaction_handles_nested_dicts() -> None:
    payload = {
        "outer": {
            "safe": "value",
            "Authorization": "secret",
        },
        "items": [
            {"ok": 1, "secret_key": "nope"},
            "text",
        ],
    }

    redacted = RedactionPipeline.redact(payload)

    assert redacted == {
        "outer": {"safe": "value"},
        "items": [{"ok": 1}, "text"],
    }


def test_redaction_truncates_strings_over_512_bytes() -> None:
    payload = {"text": "x" * 600}

    redacted = RedactionPipeline.redact(payload)

    assert redacted["text"].startswith("x" * 512)
    assert redacted["text"].endswith("...[truncated]")


def test_write_summary_appends_exactly_one_jsonl_line(monkeypatch: Any) -> None:
    calls: list[tuple[Path, str]] = []

    def _append_text_line(path: Path, line: str) -> None:
        calls.append((path, line))

    monkeypatch.setattr("meridian.lib.state.atomic.append_text_line", _append_text_line)

    summary = ExtensionInvocationSummary(
        fqid="meridian.sessions.archiveSpawn",
        caller_surface="cli",
        request_id="req-1",
        started_at="2026-04-22T12:00:00+00:00",
        duration_ms=12.5,
        success=True,
        args_redacted={"safe": "value"},
        result_redacted={"ok": True},
    )

    writer = ObservabilityWriter(Path("/tmp/obs.jsonl"))
    writer.write_summary(summary)

    assert len(calls) == 1
    assert calls[0][0] == Path("/tmp/obs.jsonl")
    line_json = json.loads(calls[0][1])
    assert line_json["fqid"] == "meridian.sessions.archiveSpawn"
    assert line_json["success"] is True
    assert line_json["args_redacted"] == {"safe": "value"}
    assert line_json["result_redacted"] == {"ok": True}


def test_write_summary_failure_logs_to_stderr_without_raising(
    monkeypatch: Any,
    capsys: Any,
) -> None:
    def _append_text_line(_path: Path, _line: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("meridian.lib.state.atomic.append_text_line", _append_text_line)

    summary = ExtensionInvocationSummary(
        fqid="meridian.test.ping",
        caller_surface="http",
        request_id=None,
        started_at="2026-04-22T12:00:00+00:00",
        duration_ms=2.0,
        success=False,
        error_code="E_FAIL",
    )

    writer = ObservabilityWriter(Path("/tmp/obs.jsonl"))
    writer.write_summary(summary)

    captured = capsys.readouterr()
    assert "[observability] Failed to write summary: disk full" in captured.err


def test_invocation_timer_tracks_start_time_and_duration(monkeypatch: Any) -> None:
    perf_values = iter([1.0, 1.25])
    monkeypatch.setattr(
        "meridian.lib.extensions.observability.time.perf_counter",
        lambda: next(perf_values),
    )

    timer = InvocationTimer()

    started_at = datetime.fromisoformat(timer.started_at)
    assert started_at.tzinfo is not None
    assert timer.duration_ms == 250.0
