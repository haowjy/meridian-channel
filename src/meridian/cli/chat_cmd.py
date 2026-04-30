"""CLI command for the local headless chat backend."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, cast
from urllib.parse import urlparse

from cyclopts import App, Parameter

from meridian.lib.chat.backend_acquisition import ColdSpawnAcquisition
from meridian.lib.chat.normalization.base import EventNormalizer
from meridian.lib.chat.normalization.registry import get_normalizer_factory
from meridian.lib.chat.runtime import ChatRuntime, PipelineLookup
from meridian.lib.harness.ids import HarnessId
from meridian.lib.harness.launch_spec import (
    ClaudeLaunchSpec,
    CodexLaunchSpec,
    OpenCodeLaunchSpec,
)
from meridian.lib.launch.launch_types import ResolvedLaunchSpec
from meridian.lib.safety.permissions import UnsafeNoOpPermissionResolver
from meridian.lib.state.user_paths import get_user_home
from meridian.lib.streaming.spawn_manager import SpawnManager

CHAT_SERVER_FILE = "chat-server.json"


def register_chat_command(app: App) -> None:
    """Register the ``meridian chat`` command and management subcommands."""

    chat_app = App(
        name="chat",
        help="Start or manage the local chat backend.",
        help_formatter="plain",
    )
    app.command(chat_app, name="chat")
    chat_app.default(_chat)
    chat_app.command(name="ls")(_chat_ls)
    chat_app.command(name="show")(_chat_show)
    chat_app.command(name="log")(_chat_log)
    chat_app.command(name="close")(_chat_close)


def _chat(
    model: Annotated[
        str | None,
        Parameter(name=["--model", "-m"], help="Model id or alias for chat backends."),
    ] = None,
    harness: Annotated[
        str | None,
        Parameter(name="--harness", help="Harness id: claude, codex, or opencode."),
    ] = None,
    port: Annotated[int, Parameter(name="--port", help="Port to bind; 0 auto-assigns.")] = 0,
    host: Annotated[
        str,
        Parameter(name="--host", help="Host/interface to bind."),
    ] = "127.0.0.1",
    headless: Annotated[
        bool,
        Parameter(name="--headless", help="Run API-only backend; --no-headless is reserved."),
    ] = True,
) -> None:
    """Start the local chat backend server."""

    from meridian.cli.main import get_global_options

    effective_harness = harness or get_global_options().harness
    run_chat_server(
        model=model,
        harness=effective_harness,
        port=port,
        host=host,
        headless=headless,
    )


def _chat_ls(
    url: Annotated[str | None, Parameter(name="--url", help="Chat server base URL.")] = None,
) -> None:
    response = _request_json("GET", "/chat", url=url)
    rows = response.get("chats", [])
    if not isinstance(rows, list):
        raise ValueError("invalid chat server response: chats must be a list")
    print(_format_chat_table(cast("list[dict[str, object]]", rows)))


def _chat_show(
    chat_id: Annotated[str, Parameter(help="Chat id to inspect.")],
    url: Annotated[str | None, Parameter(name="--url", help="Chat server base URL.")] = None,
) -> None:
    state = _request_json("GET", f"/chat/{chat_id}/state", url=url)
    events = _request_json("GET", f"/chat/{chat_id}/events?last=5", url=url)
    print(f"chat_id: {state.get('chat_id', chat_id)}")
    print(f"state: {state.get('state', 'unknown')}")
    print("events:")
    for event in _events_from_response(events):
        print(f"  {_format_event_summary(event)}")


def _chat_log(
    chat_id: Annotated[str, Parameter(help="Chat id to read.")],
    url: Annotated[str | None, Parameter(name="--url", help="Chat server base URL.")] = None,
    last: Annotated[
        int | None,
        Parameter(name="--last", help="Show only the last N events."),
    ] = None,
    follow: Annotated[
        bool,
        Parameter(name="--follow", help="Follow live events over WebSocket."),
    ] = False,
) -> None:
    query = f"?last={last}" if last is not None else ""
    response = _request_json("GET", f"/chat/{chat_id}/events{query}", url=url)
    events = _events_from_response(response)
    for event in events:
        print(json.dumps(event, sort_keys=True))
    if follow:
        last_seq = _last_seq(events)
        asyncio.run(_follow_chat_log(chat_id, url=url, last_seq=last_seq))


def _chat_close(
    chat_id: Annotated[str, Parameter(help="Chat id to close.")],
    url: Annotated[str | None, Parameter(name="--url", help="Chat server base URL.")] = None,
) -> None:
    response = _request_json("POST", f"/chat/{chat_id}/close", url=url)
    status = response.get("status", "unknown")
    if status != "accepted":
        error = response.get("error", "unknown")
        raise ValueError(f"chat close rejected: {error}")
    print(f"closed {chat_id}")


def run_chat_server(
    *,
    model: str | None = None,
    harness: str | None = None,
    port: int = 0,
    host: str = "127.0.0.1",
    headless: bool = True,
    uvicorn_run: Callable[..., Any] | None = None,
    stdout: Any | None = None,
) -> int:
    """Configure and run the local chat backend; return the bound port."""

    import uvicorn

    from meridian.lib.chat.server import app as chat_app
    from meridian.lib.chat.server import configure

    if port < 0 or port > 65535:
        raise ValueError("port must be between 0 and 65535")

    runtime_root = get_user_home()
    project_root = Path.cwd()
    harness_id = _resolve_harness_id(harness)
    runtime = ChatRuntime(
        runtime_root=runtime_root,
        project_root=project_root,
        acquisition_factory=_ChatBackendAcquisitionFactory(
            harness_id=harness_id,
            model=(model or "").strip() or None,
        ),
    )
    configure(runtime=runtime)

    env_port = int(os.environ.get("PORT", "0") or "0")
    actual_port = port if port != 0 else (env_port or _find_free_port(host))
    output = stdout if stdout is not None else sys.stdout
    if not headless:
        print("frontend not yet available, running in headless mode", file=output, flush=True)
    print(f"Chat backend: http://{host}:{actual_port}", file=output, flush=True)
    _write_server_discovery(host=host, port=actual_port, runtime_root=runtime_root)
    runner = uvicorn_run or uvicorn.run
    runner(chat_app, host=host, port=actual_port)
    return actual_port


def _resolve_harness_id(harness: str | None) -> HarnessId:
    raw = (harness or HarnessId.CLAUDE.value).strip().lower()
    try:
        return HarnessId(raw)
    except ValueError as exc:
        valid = ", ".join(item.value for item in HarnessId)
        raise ValueError(f"unsupported chat harness {raw!r}; expected one of: {valid}") from exc


def _find_free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _write_server_discovery(*, host: str, port: int, runtime_root: Path) -> None:
    path = runtime_root / CHAT_SERVER_FILE
    display_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    payload = {"host": host, "port": port, "url": f"http://{display_host}:{port}"}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _server_discovery_path() -> Path:
    return get_user_home() / CHAT_SERVER_FILE


def _resolve_server_url(url: str | None) -> str:
    if url is not None and url.strip():
        return url.rstrip("/")
    path = _server_discovery_path()
    if not path.exists():
        raise ValueError("chat server URL not found; start `meridian chat` or pass --url")
    try:
        data = cast("object", json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"chat server discovery file is invalid: {path}") from exc
    discovered = cast("dict[str, object]", data).get("url") if isinstance(data, dict) else None
    if not isinstance(discovered, str) or not discovered.strip():
        raise ValueError(f"chat server discovery file is missing url: {path}")
    return discovered.rstrip("/")


def _request_json(method: str, path: str, *, url: str | None) -> dict[str, object]:
    import httpx

    base_url = _resolve_server_url(url)
    try:
        response = httpx.request(method, f"{base_url}{path}", timeout=5.0)
    except httpx.HTTPError as exc:
        raise ValueError(f"failed to connect to chat server at {base_url}: {exc}") from exc
    if response.status_code >= 400:
        raise ValueError(f"chat server returned HTTP {response.status_code}: {response.text}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("invalid chat server response: expected object")
    return cast("dict[str, object]", payload)


def _events_from_response(response: dict[str, object]) -> list[dict[str, object]]:
    raw = response.get("events", [])
    if not isinstance(raw, list):
        raise ValueError("invalid chat server response: events must be a list")
    raw_events = cast("list[object]", raw)
    events: list[dict[str, object]] = []
    for event in raw_events:
        if isinstance(event, dict):
            events.append(cast("dict[str, object]", event))
    return events


def _format_chat_table(rows: list[dict[str, object]]) -> str:
    headers = ("chat_id", "state", "created_at")
    values = [[str(row.get(column) or "") for column in headers] for row in rows]
    widths = [len(header) for header in headers]
    for row in values:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    lines = ["  ".join(header.ljust(widths[index]) for index, header in enumerate(headers))]
    lines.append("  ".join("-" * width for width in widths))
    lines.extend(
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        for row in values
    )
    return "\n".join(lines)


def _format_event_summary(event: dict[str, object]) -> str:
    seq = event.get("seq", "?")
    event_type = event.get("type", "unknown")
    timestamp = event.get("timestamp", "")
    payload = event.get("payload")
    if isinstance(payload, dict) and payload:
        return f"#{seq} {timestamp} {event_type} {json.dumps(payload, sort_keys=True)}"
    return f"#{seq} {timestamp} {event_type}"


def _last_seq(events: list[dict[str, object]]) -> int | None:
    for event in reversed(events):
        seq = event.get("seq")
        if isinstance(seq, int):
            return seq
    return None


async def _follow_chat_log(chat_id: str, *, url: str | None, last_seq: int | None) -> None:
    import websockets

    base_url = _resolve_server_url(url)
    parsed = urlparse(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    netloc = parsed.netloc
    ws_url = f"{scheme}://{netloc}/ws/chat/{chat_id}"
    if last_seq is not None:
        ws_url = f"{ws_url}?last_seq={last_seq}"
    async with websockets.connect(ws_url) as websocket:
        async for message in websocket:
            print(message, flush=True)


@dataclass(frozen=True)
class _ChatBackendAcquisitionFactory:
    harness_id: HarnessId
    model: str | None

    def build(
        self,
        *,
        pipeline_lookup: PipelineLookup,
        project_root: Path,
        runtime_root: Path,
    ) -> ColdSpawnAcquisition:
        return _build_backend_acquisition(
            runtime_root=runtime_root,
            project_root=project_root,
            harness_id=self.harness_id,
            model=self.model,
            pipeline_lookup=pipeline_lookup,
        )


def _build_backend_acquisition(
    *,
    runtime_root: Path,
    project_root: Path,
    harness_id: HarnessId,
    model: str | None,
    pipeline_lookup: PipelineLookup,
) -> ColdSpawnAcquisition:
    manager = SpawnManager(runtime_root=runtime_root, project_root=project_root)

    return ColdSpawnAcquisition(
        spawn_manager=cast("Any", manager),
        normalizer_factory=_normalizer_factory(harness_id),
        pipeline_lookup=pipeline_lookup,
        launch_spec_factory=lambda prompt: _launch_spec(
            harness_id=harness_id,
            prompt=prompt,
            model=model,
        ),
        project_root=project_root,
        harness_id=harness_id,
    )


def _normalizer_factory(harness_id: HarnessId) -> Callable[[str, str], EventNormalizer]:
    factory = get_normalizer_factory(harness_id)

    def wrapper(chat_id: str, execution_id: str) -> EventNormalizer:
        return factory(chat_id, execution_id)

    return wrapper


def _launch_spec(*, harness_id: HarnessId, prompt: str, model: str | None) -> ResolvedLaunchSpec:
    permission_resolver = UnsafeNoOpPermissionResolver(_suppress_warning=True)
    if harness_id == HarnessId.CLAUDE:
        return ClaudeLaunchSpec(
            prompt=prompt,
            model=model,
            permission_resolver=permission_resolver,
        )
    if harness_id == HarnessId.CODEX:
        return CodexLaunchSpec(
            prompt=prompt,
            model=model,
            permission_resolver=permission_resolver,
        )
    if harness_id == HarnessId.OPENCODE:
        return OpenCodeLaunchSpec(
            prompt=prompt,
            model=model,
            permission_resolver=permission_resolver,
        )
    return ResolvedLaunchSpec(
        prompt=prompt,
        model=model,
        permission_resolver=permission_resolver,
    )


__all__ = ["register_chat_command", "run_chat_server"]
