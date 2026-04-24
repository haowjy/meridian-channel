"""Parser regressions for running-spawn query and session-log extraction."""

from __future__ import annotations

import json

from meridian.lib.ops.session_log import parse_session_file
from meridian.lib.ops.spawn.query import extract_last_assistant_message


def _jsonl(*events: dict[str, object]) -> str:
    return "\n".join(json.dumps(event) for event in events)


def _parse_messages(tmp_path, raw: str) -> list[tuple[str, str]]:
    output_path = tmp_path / "history.jsonl"
    output_path.write_text(raw + "\n", encoding="utf-8")
    segments, _ = parse_session_file(output_path)
    return [(item.role, item.content) for item in segments[0]]


def test_extract_last_assistant_message_handles_markers_and_json_events() -> None:
    codex_banner_text = "\n".join(
        [
            "OpenAI Codex v0.107.0",
            "model=gpt-5.3-codex",
            "harness=codex",
            "provider=openai",
        ]
    )
    assert extract_last_assistant_message(codex_banner_text) is None

    marker_stream_text = "\n".join(
        [
            "OpenAI Codex v0.107.0",
            "model: gpt-5.3-codex",
            "codex",
            "First response line.",
            "Second response line.",
            "exec",
            "/bin/bash -lc 'echo ok'",
            "codex",
            "Final assistant reply.",
        ]
    )
    assert extract_last_assistant_message(marker_stream_text) == "Final assistant reply."

    json_event_text = "\n".join(
        [
            json.dumps({"type": "assistant", "text": "json assistant message"}),
            "exec",
        ]
    )
    assert extract_last_assistant_message(json_event_text) == "json assistant message"


def test_session_log_parser_handles_structured_harness_events(tmp_path) -> None:
    output_path = tmp_path / "history.jsonl"
    output_path.write_text(
        _jsonl(
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "nested message"}]},
            },
            {
                "type": "assistant",
                "content": [{"type": "text", "text": "assistant fallback"}],
            },
            {
                "event_type": "item/completed",
                "harness_id": "codex",
                "payload": {
                    "item": {"type": "agentMessage", "text": "codex message"},
                },
            },
            {
                "type": "progress",
                "data": {
                    "message": {
                        "type": "assistant",
                        "message": {"content": [{"type": "text", "text": "wrapped"}]},
                    }
                },
            },
            {"type": "rate_limit_event", "message": "ignored"},
        )
        + "\n",
        encoding="utf-8",
    )

    segments, total_compactions = parse_session_file(output_path)

    assert total_compactions == 0
    assert [(item.role, item.content) for item in segments[0]] == [
        ("assistant", "nested message"),
        ("assistant", "assistant fallback"),
        ("assistant", "codex message"),
        ("assistant", "wrapped"),
    ]


def test_session_log_parser_handles_streaming_codex_event_shapes(tmp_path) -> None:
    output = _parse_messages(
        tmp_path,
        _jsonl(
            {
                "event_type": "item/completed",
                "payload": {"item": {"type": "agentMessage", "text": "streamed codex message"}},
            }
        )
    )

    assert output == [("assistant", "streamed codex message")]


def test_session_log_parser_handles_unstructured_assistant_fallbacks(tmp_path) -> None:
    output = _parse_messages(
        tmp_path,
        _jsonl(
            {"role": "assistant", "content": "generic fallback"},
            {"type": "assistant", "text": "json assistant message"},
        )
    )

    assert output == [
        ("assistant", "generic fallback"),
        ("assistant", "json assistant message"),
    ]


def test_session_log_parser_returns_empty_for_empty_or_whitespace_input(tmp_path) -> None:
    assert _parse_messages(tmp_path, "") == []
    assert _parse_messages(tmp_path, "\n \n\t\n") == []


def test_session_log_parser_skips_malformed_or_non_assistant_payloads(tmp_path) -> None:
    raw = "\n".join(
        [
            "{not-json}",
            json.dumps({"type": "item.completed", "item": {"type": "tool_call", "text": "x"}}),
            json.dumps({"type": "progress", "message": "ignored"}),
            json.dumps({"type": "assistant", "message": "kept"}),
        ]
    )

    assert _parse_messages(tmp_path, raw) == [("assistant", "kept")]
