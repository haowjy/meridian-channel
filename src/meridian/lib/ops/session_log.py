"""Session log operation with compaction-aware segment navigation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import NamedTuple, cast

from pydantic import BaseModel, ConfigDict

from meridian.lib.config.settings import resolve_project_root
from meridian.lib.core.context import RuntimeContext
from meridian.lib.core.spawn_lifecycle import is_active_spawn_status
from meridian.lib.core.types import HarnessId
from meridian.lib.core.util import FormatContext
from meridian.lib.harness.registry import get_default_harness_registry
from meridian.lib.harness.session_detection import infer_harness_from_untracked_session_ref
from meridian.lib.harness.transcript import TranscriptMessage, text_from_value
from meridian.lib.ops.reference import resolve_session_reference
from meridian.lib.ops.runtime import (
    async_from_sync,
    resolve_runtime_root_for_read,
)
from meridian.lib.ops.spawn.query import read_spawn_row
from meridian.lib.state import session_store, spawn_store

_CODEX_FILENAME_RE = re.compile(
    r"^rollout-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-(?P<session_id>[0-9a-fA-F-]{36})\.jsonl$"
)
_MAX_PREVIEW = 120


class SessionLogInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    ref: str = ""
    compaction: int = 0
    last_n: int | None = None
    offset: int = 0
    file_path: str | None = None
    repo_root: str | None = None


class SessionLogMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    index: int
    role: str
    content: str


class SessionLogOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str
    total_compactions: int
    segment: int
    segment_messages: int
    showing: str
    messages: tuple[SessionLogMessage, ...]
    has_newer: bool = False
    has_older: bool = False
    has_earlier_segments: bool = False
    source: str | None = None

    def format_text(self, ctx: FormatContext | None = None) -> str:
        _ = ctx
        message_label = "message" if self.segment_messages == 1 else "messages"
        source = f" ({self.source})" if self.source else ""
        lines = [
            f"Session {self.session_id}{source} — segment {self.segment}, "
            f"{self.segment_messages} {message_label} (showing {self.showing})"
        ]
        for message in self.messages:
            lines.append("")
            lines.append(f"--- {message.index} [{message.role}] ---")
            lines.append(message.content)
        hints: list[str] = []
        if self.has_older:
            hints.append("Use --last N to show more messages.")
        if self.has_newer:
            hints.append("Use --offset N to page forward.")
        if self.has_earlier_segments:
            hints.append("Use -c N for earlier compaction segments.")
        if hints:
            lines.append("")
            lines.extend(hints)
        return "\n".join(lines)


class _ResolvedTarget(NamedTuple):
    session_id: str
    harness: str | None
    file_path: Path
    source: str


def _normalize_text(value: str) -> str:
    return value.strip()


def _preview(value: str, *, limit: int = _MAX_PREVIEW) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3].rstrip()}..."


def _tool_use_summary(block: dict[str, object]) -> str:
    name = str(block.get("name", "tool")).strip() or "tool"
    tool_input = block.get("input")
    if not isinstance(tool_input, dict):
        return f"[tool: {name}]"

    input_payload = cast("dict[str, object]", tool_input)
    for key in ("file_path", "path", "command", "pattern", "description", "skill"):
        value = input_payload.get(key)
        if isinstance(value, str) and value.strip():
            return f"[tool: {name} {_preview(value.strip())}]"
    return f"[tool: {name}]"


def _tool_result_summary(block: dict[str, object]) -> str:
    content = text_from_value(block.get("content"))
    if not content:
        return "[tool_result]"
    return f"[tool_result] {content}"


def _extract_claude_content(role: str, content: object) -> list[TranscriptMessage]:
    messages: list[TranscriptMessage] = []

    if isinstance(content, str):
        text = _normalize_text(content)
        if text:
            messages.append(TranscriptMessage(role=role, content=text))
        return messages

    if not isinstance(content, list):
        text = text_from_value(content)
        if text:
            messages.append(TranscriptMessage(role=role, content=text))
        return messages

    blocks = cast("list[object]", content)
    for item in blocks:
        if not isinstance(item, dict):
            text = text_from_value(item)
            if text:
                messages.append(TranscriptMessage(role=role, content=text))
            continue

        block = cast("dict[str, object]", item)
        block_type = str(block.get("type", "")).strip().lower()
        if block_type == "text":
            text = text_from_value(block.get("text"))
            if text:
                messages.append(TranscriptMessage(role=role, content=text))
            continue
        if role == "assistant" and block_type == "tool_use":
            messages.append(TranscriptMessage(role=role, content=_tool_use_summary(block)))
            continue
        if role == "user" and block_type == "tool_result":
            messages.append(TranscriptMessage(role=role, content=_tool_result_summary(block)))
            continue

        text = text_from_value(block)
        if text:
            messages.append(TranscriptMessage(role=role, content=text))

    return messages


def _extract_codex_response_item(payload: dict[str, object]) -> list[TranscriptMessage]:
    item_type = str(payload.get("type", "")).strip().lower()
    if item_type == "message":
        role = str(payload.get("role", "assistant")).strip().lower() or "assistant"
        content = payload.get("content")
        messages: list[TranscriptMessage] = []
        if isinstance(content, list):
            blocks = cast("list[object]", content)
            for block in blocks:
                if not isinstance(block, dict):
                    text = text_from_value(block)
                    if text:
                        messages.append(TranscriptMessage(role=role, content=text))
                    continue
                block_payload = cast("dict[str, object]", block)
                block_type = str(block_payload.get("type", "")).strip().lower()
                if block_type in {"input_text", "output_text", "text"}:
                    text = text_from_value(block_payload.get("text"))
                    if text:
                        messages.append(TranscriptMessage(role=role, content=text))
                    continue
                text = text_from_value(block_payload)
                if text:
                    messages.append(TranscriptMessage(role=role, content=text))
        else:
            text = text_from_value(content)
            if text:
                messages.append(TranscriptMessage(role=role, content=text))
        if not messages:
            fallback = text_from_value(payload.get("text"))
            if fallback:
                messages.append(TranscriptMessage(role=role, content=fallback))
        return messages

    if item_type == "function_call":
        name = str(payload.get("name", "tool")).strip() or "tool"
        arguments = text_from_value(payload.get("arguments"))
        rendered = f"[tool: {name}]"
        if arguments:
            rendered = f"[tool: {name} {_preview(arguments)}]"
        return [TranscriptMessage(role="assistant", content=rendered)]

    if item_type == "function_call_output":
        output = text_from_value(payload.get("output"))
        if output:
            return [TranscriptMessage(role="user", content=f"[tool_result] {output}")]
        return [TranscriptMessage(role="user", content="[tool_result]")]

    return []


def _extract_codex_exec_item(item: dict[str, object]) -> list[TranscriptMessage]:
    item_type = str(item.get("type", "")).strip().lower().replace("_", "").replace("-", "")
    if item_type == "agentmessage":
        text = text_from_value(item.get("text"))
        if not text:
            return []
        return [TranscriptMessage(role="assistant", content=text)]

    if item_type == "commandexecution":
        output = text_from_value(item.get("aggregated_output") or item.get("aggregatedOutput"))
        command = text_from_value(item.get("command"))
        if output:
            return [TranscriptMessage(role="user", content=f"[tool_result] {output}")]
        if command:
            return [
                TranscriptMessage(role="assistant", content=f"[tool: bash {_preview(command)}]")
            ]

    return []


def _extract_from_event(payload: dict[str, object]) -> tuple[list[TranscriptMessage], bool]:
    raw_event_type = str(
        payload.get("event_type", payload.get("event", payload.get("type", "")))
    )
    event_type = raw_event_type.strip().lower().replace("/", ".")

    if "event_type" in payload and isinstance(payload.get("payload"), dict):
        nested = dict(cast("dict[str, object]", payload["payload"]))
        nested.setdefault("event_type", payload["event_type"])
        return _extract_from_event(nested)

    # Claude compaction boundary.
    is_boundary = (
        event_type == "system"
        and str(payload.get("subtype", "")).strip().lower() == "compact_boundary"
    )

    # Claude live progress wrappers embed assistant/user events at data.message.
    if event_type == "progress":
        data = payload.get("data")
        if isinstance(data, dict):
            nested_message = cast("dict[str, object]", data).get("message")
            if isinstance(nested_message, dict):
                nested_messages, nested_boundary = _extract_from_event(
                    cast("dict[str, object]", nested_message)
                )
                return nested_messages, is_boundary or nested_boundary
        return ([], is_boundary)

    if event_type in {"assistant", "user"}:
        role = event_type
        message = payload.get("message")
        if isinstance(message, dict):
            content = cast("dict[str, object]", message).get("content")
            extracted = _extract_claude_content(role, content)
            if extracted:
                return extracted, is_boundary
        extracted = _extract_claude_content(role, payload.get("content"))
        if extracted:
            return extracted, is_boundary
        raw_text = message if isinstance(message, str) else payload.get("text")
        text = text_from_value(raw_text)
        if text:
            return ([TranscriptMessage(role=role, content=text)], is_boundary)
        fallback_text = text_from_value(payload.get("tool_use_result"))
        if role == "user" and fallback_text:
            return (
                [TranscriptMessage(role="user", content=f"[tool_result] {fallback_text}")],
                is_boundary,
            )
        return ([], is_boundary)

    # Codex native session file.
    if event_type == "response_item":
        raw_payload = payload.get("payload")
        if isinstance(raw_payload, dict):
            extracted = _extract_codex_response_item(cast("dict[str, object]", raw_payload))
            return (extracted, is_boundary)
        return ([], is_boundary)

    # Codex spawn output style (also valid JSONL input for --file).
    if event_type == "item.completed":
        item = payload.get("item")
        if isinstance(item, dict):
            return (_extract_codex_exec_item(cast("dict[str, object]", item)), is_boundary)
        return ([], is_boundary)

    # Generic fallback for simple role/content payloads.
    role = str(payload.get("role", "")).strip().lower()
    if role in {"assistant", "user", "system"}:
        text = text_from_value(payload.get("content"))
        if text:
            return ([TranscriptMessage(role=role, content=text)], is_boundary)

    return ([], is_boundary)


def parse_session_file(path: Path) -> tuple[list[list[TranscriptMessage]], int]:
    segments: list[list[TranscriptMessage]] = [[]]
    total_compactions = 0

    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload_obj = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload_obj, dict):
                continue
            payload = cast("dict[str, object]", payload_obj)
            extracted, boundary = _extract_from_event(payload)
            if boundary:
                total_compactions += 1
                segments.append([])
                continue
            if extracted:
                segments[-1].extend(extracted)

    return segments, total_compactions


def _extract_session_id_from_path(path: Path) -> str:
    if path.suffix == ".jsonl" and path.stem:
        codex_match = _CODEX_FILENAME_RE.match(path.name)
        if codex_match is not None:
            return codex_match.group("session_id")
        return path.stem
    return path.name


def _resolve_file_target(file_path: str) -> _ResolvedTarget:
    resolved = Path(file_path).expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Session file '{resolved.as_posix()}' not found")

    harness: str | None = None
    parts = set(resolved.parts)
    if ".claude" in parts:
        harness = "claude"
    elif ".codex" in parts:
        harness = "codex"

    return _ResolvedTarget(
        session_id=_extract_session_id_from_path(resolved),
        harness=harness,
        file_path=resolved,
        source="file",
    )


def _resolve_harness_session_file(
    *,
    repo_root: Path,
    session_id: str,
    harness: str | None,
) -> _ResolvedTarget:
    normalized_session_id = session_id.strip()
    if not normalized_session_id:
        raise FileNotFoundError("Session ID is required to resolve harness session file")

    registry = get_default_harness_registry()
    normalized_harness = (harness or "").strip().lower() or None
    if normalized_harness is not None:
        try:
            harness_id = HarnessId(normalized_harness)
            adapter = registry.get_subprocess_harness(harness_id)
        except (ValueError, KeyError, TypeError) as exc:
            raise FileNotFoundError(
                f"Session file for '{normalized_session_id}' "
                f"(harness={normalized_harness}) not found"
            ) from exc

        candidate = adapter.resolve_session_file(
            repo_root=repo_root,
            session_id=normalized_session_id,
        )
        if candidate is not None and candidate.is_file():
            return _ResolvedTarget(
                session_id=normalized_session_id,
                harness=str(harness_id),
                file_path=candidate,
                source=f"{harness_id} transcript",
            )
        raise FileNotFoundError(
            f"Session file for '{normalized_session_id}' (harness={normalized_harness}) not found"
        )

    checked_harnesses: list[str] = []
    for harness_id in registry.ids():
        try:
            adapter = registry.get_subprocess_harness(harness_id)
        except TypeError:
            continue
        checked_harnesses.append(str(harness_id))
        candidate = adapter.resolve_session_file(
            repo_root=repo_root,
            session_id=normalized_session_id,
        )
        if candidate is not None and candidate.is_file():
            return _ResolvedTarget(
                session_id=normalized_session_id,
                harness=str(harness_id),
                file_path=candidate,
                source=f"{harness_id} transcript",
            )

    checked = ", ".join(checked_harnesses) if checked_harnesses else "<none>"
    raise FileNotFoundError(
        f"Session file for '{normalized_session_id}' not found. Checked harnesses: {checked}"
    )


def _spawn_output_path(state_root: Path, spawn_id: str, *, live_first: bool) -> Path | None:
    live_path = state_root / "spawns" / spawn_id / "output.jsonl"
    artifact_path = state_root / "artifacts" / spawn_id / "output.jsonl"
    candidates = (
        (live_path, artifact_path) if live_first else (artifact_path, live_path)
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _target_from_spawn_output(
    state_root: Path,
    *,
    display_id: str,
    spawn_id: str,
    live_first: bool,
) -> _ResolvedTarget | None:
    output_path = _spawn_output_path(state_root, spawn_id, live_first=live_first)
    if output_path is None:
        return None
    return _ResolvedTarget(
        session_id=display_id,
        harness=None,
        file_path=output_path,
        source=f"spawn {spawn_id} output",
    )


def _primary_spawn_for_chat(state_root: Path, chat_id: str) -> spawn_store.SpawnRecord | None:
    from meridian.lib.state.reaper import reconcile_spawns

    spawns = reconcile_spawns(
        state_root,
        spawn_store.list_spawns(state_root, filters={"chat_id": chat_id}),
    )
    primary_spawns = [row for row in spawns if row.kind == "primary"]
    if not primary_spawns:
        return None
    return primary_spawns[-1]


def _resolve_from_chat_id(
    *,
    repo_root: Path,
    state_root: Path,
    chat_id: str,
) -> _ResolvedTarget:
    resolved = resolve_session_reference(repo_root, chat_id)
    if not resolved.tracked:
        raise ValueError(f"Chat '{chat_id}' not found")
    primary_spawn = _primary_spawn_for_chat(state_root, chat_id)
    if (
        primary_spawn is not None
        and is_active_spawn_status(primary_spawn.status)
        and (
            output_target := _target_from_spawn_output(
                state_root,
                display_id=chat_id,
                spawn_id=primary_spawn.id,
                live_first=True,
            )
        )
        is not None
    ):
        return output_target

    if resolved.missing_harness_session_id:
        # Fallback: check if the primary spawn for this chat has a harness session id
        spawns = spawn_store.list_spawns(state_root, filters={"chat_id": chat_id})
        fallback_session_id: str | None = None
        fallback_harness: str | None = resolved.harness
        for spawn in spawns:
            sid = (spawn.harness_session_id or "").strip()
            if sid:
                fallback_session_id = sid
                if spawn.harness:
                    fallback_harness = spawn.harness.strip() or fallback_harness
                break
        if fallback_session_id:
            return _resolve_harness_session_file(
                repo_root=repo_root,
                session_id=fallback_session_id,
                harness=fallback_harness,
            )
        if primary_spawn is not None and (
            output_target := _target_from_spawn_output(
                state_root,
                display_id=chat_id,
                spawn_id=primary_spawn.id,
                live_first=True,
            )
        ):
            return output_target
        if spawns:
            raise ValueError(
                f"Session '{chat_id}' exists but no transcript is available yet "
                "(no harness session id recorded and no spawn output found)."
            )
        raise ValueError(
            f"Session '{chat_id}' exists but no transcript is available yet "
            "(no harness session id recorded)."
        )

    normalized_session_id = resolved.harness_session_id
    if normalized_session_id is None:
        raise ValueError(f"Chat '{chat_id}' not found")

    try:
        return _resolve_harness_session_file(
            repo_root=repo_root,
            session_id=normalized_session_id,
            harness=resolved.harness,
        )
    except FileNotFoundError:
        if primary_spawn is not None and (
            output_target := _target_from_spawn_output(
                state_root,
                display_id=chat_id,
                spawn_id=primary_spawn.id,
                live_first=True,
            )
        ):
            return output_target
        raise


def _resolve_from_spawn_id(
    *,
    repo_root: Path,
    state_root: Path,
    spawn_id: str,
) -> _ResolvedTarget:
    row = read_spawn_row(repo_root, spawn_id)
    if row is None:
        raise ValueError(f"Spawn '{spawn_id}' not found")

    if is_active_spawn_status(row.status) and (
        output_target := _target_from_spawn_output(
            state_root,
            display_id=spawn_id,
            spawn_id=spawn_id,
            live_first=True,
        )
    ):
        return output_target

    session_id = (row.harness_session_id or "").strip()
    harness = (row.harness or "").strip() or None

    if not session_id and row.chat_id is not None:
        by_chat = session_store.get_session_harness_id(state_root, row.chat_id)
        session_id = (by_chat or "").strip()

    if not session_id:
        output_target = _target_from_spawn_output(
            state_root,
            display_id=spawn_id,
            spawn_id=spawn_id,
            live_first=True,
        )
        if output_target is not None:
            return output_target
        raise ValueError(
            f"Spawn '{spawn_id}' has no transcript available yet "
            "(no harness session id recorded and no spawn output found)."
        )

    if harness is None:
        record = session_store.resolve_session_ref(state_root, session_id)
        if record is not None and record.harness.strip():
            harness = record.harness.strip()

    try:
        return _resolve_harness_session_file(
            repo_root=repo_root,
            session_id=session_id,
            harness=harness,
        )
    except FileNotFoundError:
        output_target = _target_from_spawn_output(
            state_root,
            display_id=spawn_id,
            spawn_id=spawn_id,
            live_first=False,
        )
        if output_target is not None:
            return output_target
        raise


def _resolve_from_session_ref(
    *,
    repo_root: Path,
    state_root: Path,
    session_ref: str,
) -> _ResolvedTarget:
    record = session_store.resolve_session_ref(state_root, session_ref)
    if record is not None:
        session_id = record.harness_session_id.strip() or session_ref
        harness = record.harness.strip() or None
        return _resolve_harness_session_file(
            repo_root=repo_root,
            session_id=session_id,
            harness=harness,
        )

    inferred = infer_harness_from_untracked_session_ref(repo_root, session_ref)
    inferred_name = str(inferred) if inferred is not None else None
    return _resolve_harness_session_file(
        repo_root=repo_root,
        session_id=session_ref,
        harness=inferred_name,
    )


def resolve_target(
    payload: SessionLogInput, *, repo_root: Path, state_root: Path
) -> _ResolvedTarget:
    if payload.file_path is not None and payload.file_path.strip():
        return _resolve_file_target(payload.file_path)

    ref = payload.ref.strip()
    if not ref:
        raise ValueError("Session reference is required unless --file is provided")

    if ref.startswith("c") and ref[1:].isdigit():
        return _resolve_from_chat_id(repo_root=repo_root, state_root=state_root, chat_id=ref)

    if ref.startswith("p") and ref[1:].isdigit():
        return _resolve_from_spawn_id(repo_root=repo_root, state_root=state_root, spawn_id=ref)

    return _resolve_from_session_ref(repo_root=repo_root, state_root=state_root, session_ref=ref)


def _select_segment(
    segments: list[list[TranscriptMessage]],
    *,
    compaction: int,
) -> list[TranscriptMessage]:
    if compaction < 0:
        raise ValueError("compaction must be >= 0")

    segment_index = len(segments) - 1 - compaction
    if segment_index < 0:
        raise ValueError(
            f"Compaction segment {compaction} out of range (available: 0-{len(segments) - 1})"
        )
    return segments[segment_index]


def _paginate_messages(
    messages: list[TranscriptMessage],
    *,
    last_n: int | None,
    offset: int,
) -> tuple[list[TranscriptMessage], int]:
    if offset < 0:
        raise ValueError("offset must be >= 0")
    if last_n is not None and last_n < 0:
        raise ValueError("last_n must be >= 0")

    total = len(messages)
    if offset >= total:
        return ([], total)

    end = total - offset
    start = 0 if last_n is None else max(end - last_n, 0)

    return (messages[start:end], start)


def _showing_window(messages: tuple[SessionLogMessage, ...]) -> str:
    if not messages:
        return "0-0"
    return f"{messages[0].index}-{messages[-1].index}"


def session_log_sync(
    payload: SessionLogInput,
    ctx: RuntimeContext | None = None,
) -> SessionLogOutput:
    _ = ctx
    explicit_repo_root = (
        Path(payload.repo_root).expanduser().resolve() if payload.repo_root else None
    )
    repo_root = resolve_project_root(explicit_repo_root)
    state_root = resolve_runtime_root_for_read(repo_root)

    target = resolve_target(payload, repo_root=repo_root, state_root=state_root)
    segments, total_compactions = parse_session_file(target.file_path)
    segment_messages = _select_segment(segments, compaction=payload.compaction)

    selected, start_index = _paginate_messages(
        segment_messages,
        last_n=payload.last_n,
        offset=payload.offset,
    )

    output_messages = tuple(
        SessionLogMessage(index=start_index + idx + 1, role=item.role, content=item.content)
        for idx, item in enumerate(selected)
    )

    return SessionLogOutput(
        session_id=target.session_id,
        total_compactions=total_compactions,
        segment=payload.compaction,
        segment_messages=len(segment_messages),
        showing=_showing_window(output_messages),
        messages=output_messages,
        has_newer=payload.offset > 0,
        has_older=start_index > 0,
        has_earlier_segments=total_compactions > payload.compaction,
        source=target.source,
    )


session_log = async_from_sync(session_log_sync)


__all__ = [
    "SessionLogInput",
    "SessionLogMessage",
    "SessionLogOutput",
    "parse_session_file",
    "resolve_target",
    "session_log",
    "session_log_sync",
]
