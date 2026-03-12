"""Low-level subprocess stream capture helpers.

Separates byte framing and artifact-file persistence from runner policy so the
execution path can reason in terms of process lifecycle rather than pipe
mechanics.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import cast

import structlog

from meridian.lib.harness.adapter import StreamEvent
from meridian.lib.safety.redaction import SecretSpec, redact_secret_bytes

logger = structlog.get_logger(__name__)

DEFAULT_STREAM_READ_CHUNK_SIZE = 64 * 1024


def _extract_tokens_payload(raw_line: bytes) -> bytes | None:
    try:
        payload_obj = json.loads(raw_line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None

    if not isinstance(payload_obj, dict):
        return None

    payload = cast("dict[str, object]", payload_obj)
    tokens = payload.get("tokens")
    if not isinstance(tokens, dict):
        return None
    return json.dumps(tokens, sort_keys=True).encode("utf-8")


def extract_latest_tokens_payload(output_bytes: bytes) -> bytes | None:
    latest_payload: bytes | None = None
    for raw_line in output_bytes.splitlines():
        parsed = _extract_tokens_payload(raw_line)
        if parsed is not None:
            latest_payload = parsed
    return latest_payload


async def _iter_stream_lines(
    reader: asyncio.StreamReader,
    *,
    chunk_size: int = DEFAULT_STREAM_READ_CHUNK_SIZE,
) -> AsyncIterator[bytes]:
    pending = bytearray()
    while True:
        chunk = await reader.read(chunk_size)
        if not chunk:
            break
        pending.extend(chunk)
        while True:
            newline_index = pending.find(b"\n")
            if newline_index < 0:
                break
            line = bytes(pending[: newline_index + 1])
            del pending[: newline_index + 1]
            yield line
    if pending:
        yield bytes(pending)


async def capture_stdout_stream(
    reader: asyncio.StreamReader,
    output_file: Path,
    *,
    secrets: tuple[SecretSpec, ...],
    line_observer: Callable[[bytes], None] | None,
    parse_stream_event: Callable[[str], StreamEvent | None] | None = None,
    event_observer: Callable[[StreamEvent], None] | None = None,
    stream_to_terminal: bool = False,
) -> bytes | None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    last_tokens_payload: bytes | None = None

    with output_file.open("wb") as handle:
        async for raw_line in _iter_stream_lines(reader):
            redacted_line = redact_secret_bytes(raw_line, secrets)
            if line_observer is not None:
                line_observer(redacted_line)

            line_text = redacted_line.decode("utf-8", errors="replace")
            if parse_stream_event is not None and event_observer is not None:
                try:
                    parsed_event = parse_stream_event(line_text)
                except Exception:
                    logger.warning("Failed to parse harness stream event.", exc_info=True)
                else:
                    if parsed_event is not None:
                        try:
                            event_observer(parsed_event)
                        except Exception:
                            logger.warning("Stream event observer failed.", exc_info=True)

            if stream_to_terminal:
                sys.stderr.write(line_text)
                sys.stderr.flush()

            parsed_tokens = _extract_tokens_payload(raw_line)
            if parsed_tokens is not None:
                last_tokens_payload = redact_secret_bytes(parsed_tokens, secrets)

            handle.write(redacted_line)
            handle.flush()

    return last_tokens_payload


async def capture_stderr_stream(
    reader: asyncio.StreamReader,
    stderr_file: Path,
    *,
    secrets: tuple[SecretSpec, ...],
    stream_to_terminal: bool = False,
    chunk_size: int = DEFAULT_STREAM_READ_CHUNK_SIZE,
) -> bytes:
    stderr_file.parent.mkdir(parents=True, exist_ok=True)
    buffer = bytearray()

    with stderr_file.open("wb") as handle:
        while True:
            chunk = await reader.read(chunk_size)
            if not chunk:
                break
            redacted_chunk = redact_secret_bytes(chunk, secrets)
            handle.write(redacted_chunk)
            handle.flush()
            buffer.extend(redacted_chunk)
            if stream_to_terminal:
                sys.stderr.write(redacted_chunk.decode("utf-8", errors="replace"))
                sys.stderr.flush()

    return bytes(buffer)
