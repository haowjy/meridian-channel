# DebugTracer: Contract, Schema, and Hooks

## DebugTracer Class

A single class in a new module `src/meridian/lib/observability/debug_tracer.py`:

```python
class DebugTracer:
    """Structured JSONL debug event writer for streaming pipeline observability.

    Contract: emit() is best-effort and never raises. If the underlying file
    write or serialization fails, the tracer logs one warning and disables
    itself for the remainder of the session.
    """

    def __init__(
        self,
        spawn_id: str,
        debug_path: Path,
        *,
        echo_stderr: bool = False,
        max_payload_bytes: int = 4096,
    ) -> None: ...

    def emit(
        self,
        layer: str,
        event: str,
        *,
        direction: str = "internal",
        data: dict[str, object] | None = None,
    ) -> None:
        """Append one structured debug event. Never raises.

        If the underlying write fails, logs a warning on the first failure,
        sets self._disabled = True, and returns silently on all subsequent calls.
        """
        ...

    def close(self) -> None:
        """Flush and close the debug file handle. Idempotent."""
        ...
```

**Key properties:**
- **Non-raising.** `emit()` wraps all internal operations (serialization, file I/O, stderr echo) in `try/except Exception`. On first failure, logs one `logger.warning` and sets `self._disabled = True`. All subsequent `emit()` calls return immediately. The tracer must never crash the pipeline it observes.
- **Synchronous.** Appends one line to an open file handle. No async machinery — debug tracing must not introduce event loop pressure or backpressure.
- **Thread-safe** via `threading.Lock` on the file handle, since `emit()` can be called from `asyncio.to_thread` paths (e.g., the `_append_jsonl` helper).
- **Lazy file open with dir creation.** The handle opens on first `emit()`, not in `__init__`, so creating a tracer has zero I/O cost. On first open, creates parent directories (`path.parent.mkdir(parents=True, exist_ok=True)`) to handle the case where the first trace event fires before the spawn directory is created by the adapter.
- **Idempotent close.** `close()` can be called multiple times safely. Called from SpawnManager cleanup.

## Shared Trace Helpers

Module-level functions in `src/meridian/lib/observability/trace_helpers.py` centralize repetitive trace patterns to prevent drift across adapters:

```python
def trace_state_change(
    tracer: DebugTracer | None,
    harness: str,
    from_state: str,
    to_state: str,
) -> None:
    """Emit a connection state_change event if tracer is active."""

def trace_wire_send(
    tracer: DebugTracer | None,
    event_name: str,
    payload: str,
    **extra: object,
) -> None:
    """Emit an outbound wire event if tracer is active."""

def trace_wire_recv(
    tracer: DebugTracer | None,
    event_name: str,
    raw_text: str,
    **extra: object,
) -> None:
    """Emit an inbound wire event if tracer is active."""

def trace_parse_error(
    tracer: DebugTracer | None,
    harness: str,
    raw_text: str,
    error: str | None = None,
) -> None:
    """Emit a parse_error or frame_dropped event if tracer is active."""
```

Each helper does the `if tracer is not None` check internally, so call sites are one line:

```python
trace_state_change(self._tracer, "claude", self._state, next_state)
```

## JSONL Event Schema

Each line in `debug.jsonl` is one JSON object:

```json
{
  "ts": 1712700000.123,
  "spawn_id": "p42",
  "layer": "wire",
  "direction": "outbound",
  "event": "stdin_write",
  "data": {
    "payload": "{\"type\":\"user\",\"message\":{\"role\":\"user\",\"content\":\"hello\"}}",
    "bytes": 67
  }
}
```

| Field | Type | Description |
|---|---|---|
| `ts` | float | Unix timestamp from `time.time()` |
| `spawn_id` | string | Spawn identifier for correlation |
| `layer` | string | Pipeline layer: `wire`, `connection`, `drain`, `mapper`, `websocket` |
| `direction` | string | `inbound`, `outbound`, or `internal` (state changes) |
| `event` | string | What happened — machine-greppable identifier |
| `data` | object \| null | Event-specific payload, truncated per `max_payload_bytes` |

### Payload Truncation

Wire payloads (the `payload` field within `data`) are truncated to `max_payload_bytes` (default 4096). Truncation appends `...[truncated, {original_bytes}B total]` so you know data was lost and how much. Non-payload fields (byte counts, status codes, state names) are never truncated.

### Data Serialization and Truncation

`emit()` processes `data` dict values before writing:
- **String values:** truncated directly via `_truncate()`.
- **Dict/list values:** serialized to JSON first (`json.dumps`), then truncated as a string. This preserves JSON structure up to the truncation point.
- **Non-serializable values:** fall back to `repr()`, then truncate.

```python
def _prepare_data(self, data: dict[str, object]) -> dict[str, object]:
    """Serialize and truncate data values for JSONL output."""
    result: dict[str, object] = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = self._truncate(value)
        elif isinstance(value, (dict, list)):
            try:
                serialized = json.dumps(value, ensure_ascii=False)
            except (TypeError, ValueError):
                serialized = repr(value)
            result[key] = self._truncate(serialized)
        else:
            result[key] = value  # int, float, bool, None — pass through
    return result

def _truncate(self, value: str) -> str:
    if len(value) <= self._max_payload_bytes:
        return value
    return value[:self._max_payload_bytes] + f"...[truncated, {len(value)}B total]"
```

## ConnectionConfig Change

Add one field to `ConnectionConfig` in `base.py`:

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from meridian.lib.observability.debug_tracer import DebugTracer

@dataclass(frozen=True)
class ConnectionConfig:
    # ... existing fields ...
    debug_tracer: DebugTracer | None = None
```

Uses `TYPE_CHECKING` guard to avoid a runtime import from `lib/observability/` into `lib/harness/connections/`. At runtime, the field is just `None | object`, which is sufficient since concrete adapters import `DebugTracer` directly when they need to call `emit()`.

## Module Placement

```
src/meridian/lib/observability/
    __init__.py
    debug_tracer.py    # DebugTracer class
    trace_helpers.py   # Shared trace helper functions
```

`lib/observability/` is a neutral package with no dependencies on `lib/harness/`, `lib/streaming/`, or `lib/app/`. Any layer can import from it without creating circular dependencies. This avoids the anti-pattern of `lib/harness/connections/` depending upward on `lib/streaming/`.

## Instrumentation Hooks by Layer

### Layer 1: Wire — Harness Connection Adapters

Each concrete connection stores `self._tracer = config.debug_tracer` during `start()` and uses shared trace helpers.

#### ClaudeConnection (stdin/stdout)

| Hook location | Event name | Direction | Data |
|---|---|---|---|
| `_send_json()` after serialization | `stdin_write` | outbound | `{payload, bytes}` |
| `events()` after `readline()` | `stdout_line` | inbound | `{raw_text, bytes}` |
| `events()` after `_parse_stdout_line()` | `parsed_event` | inbound | `{event_type, payload}` |
| `events()` on parse failure / empty parse | `parse_error` | inbound | `{raw_text, error}` |
| `_signal_process()` | `signal_sent` | outbound | `{signal}` |

```python
# In _send_json, after building wire string:
trace_wire_send(self._tracer, "stdin_write", wire, bytes=len(wire.encode("utf-8")))
```

#### CodexConnection (WebSocket)

**Prerequisite:** Codex adapter must first be refactored to use a centralized `_transition()` method (see D10). Currently mutates `self._state` directly at 7 sites.

| Hook location | Event name | Direction | Data |
|---|---|---|---|
| `_request()` before `ws.send()` | `ws_send_request` | outbound | `{method, request_id, payload}` |
| `_notify()` before `ws.send()` | `ws_send_notify` | outbound | `{method, payload}` |
| `_read_messages_loop()` on raw message | `ws_recv` | inbound | `{raw_text, bytes}` |
| `_read_messages_loop()` on response dispatch | `ws_recv_response` | inbound | `{request_id, has_error}` |
| `_read_messages_loop()` on notification dispatch | `ws_recv_notification` | inbound | `{method, payload}` |
| `_parse_jsonrpc()` returns None | `frame_dropped` | inbound | `{raw_text, reason: "malformed_json_rpc"}` |

```python
# In _request, before ws.send:
trace_wire_send(self._tracer, "ws_send_request", json.dumps(payload),
                method=method, request_id=request_id)
```

#### OpenCodeConnection (HTTP)

| Hook location | Event name | Direction | Data |
|---|---|---|---|
| `_post_json()` before request (non-probe) | `http_post` | outbound | `{path, payload}` |
| `_post_json()` after response (non-probe) | `http_response` | inbound | `{path, status, body}` |
| `_health_endpoint_ready()` attempt | `http_probe` | internal | `{path, status, is_probe: true}` |
| `_create_session()` path attempt | `http_probe` | internal | `{path, status, is_probe: true, attempt, total}` |
| `_open_event_stream()` on connect | `sse_connect` | inbound | `{path, status}` |
| `events()` on parsed stream line | `sse_event` | inbound | `{event_type, payload}` |
| `_event_from_json_line()` on malformed JSON | `parse_error` | inbound | `{raw_text, reason: "malformed_json"}` |

Path probing events use `http_probe` event name to separate them from real traffic. This prevents startup discovery noise from overwhelming the trace.

### Layer 1b: Connection State Transitions

All three adapters trace state transitions via `trace_state_change()` helper:

| Hook location | Event name | Direction | Data |
|---|---|---|---|
| `_set_state()` / `_transition()` | `state_change` | internal | `{from_state, to_state, harness}` |

```python
# In ClaudeConnection._set_state, after validation:
trace_state_change(self._tracer, "claude", self._state, next_state)
```

### Layer 2: SpawnManager._drain_loop

**The tracer is passed directly as a parameter to `_drain_loop()`, not looked up from SpawnSession.** This eliminates the timing race where the drain task starts before SpawnSession is registered.

```python
# Updated signature:
async def _drain_loop(
    self,
    spawn_id: SpawnId,
    receiver: HarnessReceiver,
    tracer: DebugTracer | None,  # passed directly
) -> None:
```

The tracer is also stored on `SpawnSession` for access by other components (ws_endpoint, cleanup):

```python
@dataclass
class SpawnSession:
    connection: HarnessConnection
    drain_task: asyncio.Task[None]
    subscriber: asyncio.Queue[HarnessEvent | None] | None
    control_server: ControlSocketServer
    started_monotonic: float
    debug_tracer: DebugTracer | None  # for ws_endpoint access and cleanup
```

| Hook location | Event name | Direction | Data |
|---|---|---|---|
| Top of drain loop iteration | `event_received` | inbound | `{event_type, harness_id}` |
| After `_append_jsonl` success | `event_persisted` | outbound | `{event_type}` |
| On `_append_jsonl` failure | `persist_error` | internal | `{event_type, error, consecutive_failures}` |
| In `_fan_out_event` on delivery | `event_fanout` | outbound | `{event_type, queue_size}` |
| In `_fan_out_event` on drop (queue full) | `event_dropped` | internal | `{event_type, reason: "backpressure"}` |

### Layer 3: AG-UI Mapper (traced from outside)

The `AGUIMapper` Protocol is NOT modified. Instead, `ws_endpoint._outbound_loop` wraps the `mapper.translate()` call. **Mapper traces include truncated payload and raw_text** so you can see why events are dropped:

```python
# In _outbound_loop:
if tracer is not None:
    tracer.emit("mapper", "translate_input", direction="inbound", data={
        "event_type": event.event_type,
        "harness_id": event.harness_id,
        "payload": event.payload,      # truncated by tracer
        "raw_text": event.raw_text,    # truncated by tracer
    })

translated = mapper.translate(event)

if tracer is not None:
    tracer.emit("mapper", "translate_output", direction="outbound", data={
        "input_event_type": event.event_type,
        "output_count": len(translated),
        "output_types": [getattr(e, "type", "unknown") for e in translated],
    })
```

This captures the malformed payloads that cause mappers to return `[]`, which is the primary diagnostic need.

### Layer 4: WebSocket Bridge

The `_outbound_loop` and `_inbound_loop` signatures gain a `tracer: DebugTracer | None` parameter. The `spawn_websocket` function extracts the tracer from `SpawnSession` via `SpawnManager` and passes it down.

| Hook location | Event name | Direction | Data |
|---|---|---|---|
| `_send_event()` | `ws_send` | outbound | `{event_type, serialized_bytes}` |
| `_inbound_loop` on receive | `ws_recv` | inbound | `{message_type, raw_text}` |
| `_inbound_loop` on control dispatch | `control_dispatch` | inbound | `{action, spawn_id}` |

**How the tracer reaches ws_endpoint:**

```python
async def spawn_websocket(websocket, spawn_id, manager):
    # ... existing setup ...
    tracer = manager.get_tracer(SpawnId(spawn_id))

    outbound_task = asyncio.create_task(
        _outbound_loop(websocket, event_queue, mapper, spawn_id, tracer)
    )
    inbound_task = asyncio.create_task(
        _inbound_loop(websocket, SpawnId(spawn_id), manager, tracer)
    )
```

SpawnManager exposes tracer access through a public method:

```python
def get_tracer(self, spawn_id: SpawnId) -> DebugTracer | None:
    session = self._sessions.get(spawn_id)
    return session.debug_tracer if session is not None else None
```

## CLI Integration

### `meridian streaming serve`

Add `--debug` flag to `streaming_serve_cmd` in `main.py`. This creates a `DebugTracer` with `echo_stderr=True` and passes it through `ConnectionConfig`.

```python
# In streaming_serve():
tracer: DebugTracer | None = None
if debug:
    spawn_dir = state_root / "spawns" / str(spawn_id)
    tracer = DebugTracer(
        spawn_id=str(spawn_id),
        debug_path=spawn_dir / "debug.jsonl",
        echo_stderr=True,
    )

config = ConnectionConfig(
    # ... existing fields ...
    debug_tracer=tracer,
)
```

### `meridian app`

Add `--debug` flag to `run_app()` in `app_cmd.py`. SpawnManager stores the debug flag and creates tracers for each spawn it starts. `echo_stderr=False` in server mode.

```python
# SpawnManager gains a debug_enabled flag:
class SpawnManager:
    def __init__(self, state_root, repo_root, *, debug: bool = False):
        self._debug = debug
        # ...

    async def start_spawn(self, config):
        # If debug is enabled globally but no tracer on config, create one:
        tracer = config.debug_tracer
        if tracer is None and self._debug:
            tracer = DebugTracer(
                spawn_id=str(config.spawn_id),
                debug_path=self._spawn_dir(config.spawn_id) / "debug.jsonl",
            )
        # ... pass tracer to _drain_loop and SpawnSession ...
```

## Tracer Lifecycle (SpawnManager-owned)

SpawnManager is the single lifecycle owner:

1. **Creation:** Either passed in via `ConnectionConfig` (CLI path) or created by SpawnManager itself (app server path when `debug=True`).
2. **Storage:** Stored on `SpawnSession.debug_tracer`.
3. **Usage:** Passed directly to `_drain_loop()`. Extracted by ws_endpoint via `manager.get_tracer(spawn_id)`.
4. **Startup failure cleanup:** If `connection.start(config)` raises before `SpawnSession` is created, `start_spawn()` closes the tracer in its except block. This prevents file descriptor leaks from repeated failed starts in app server mode.
5. **Normal cleanup:** `tracer.close()` is called in both `_cleanup_completed_session()` and `stop_spawn()`:

```python
async def _cleanup_completed_session(self, spawn_id, *, status, exit_code, error=None):
    session = self._sessions.pop(spawn_id, None)
    if session is None:
        return
    if session.debug_tracer is not None:
        session.debug_tracer.close()
    # ... existing cleanup ...
```

## Files Changed

| File | Change |
|---|---|
| `src/meridian/lib/observability/__init__.py` | **NEW** — package init |
| `src/meridian/lib/observability/debug_tracer.py` | **NEW** — DebugTracer class |
| `src/meridian/lib/observability/trace_helpers.py` | **NEW** — shared trace helper functions |
| `src/meridian/lib/harness/connections/base.py` | Add `debug_tracer` field to `ConnectionConfig` |
| `src/meridian/lib/harness/connections/claude_ws.py` | Add wire + state trace hooks via helpers |
| `src/meridian/lib/harness/connections/codex_ws.py` | **Prereq:** centralize `_transition()`. Then add wire + state + frame_dropped hooks |
| `src/meridian/lib/harness/connections/opencode_http.py` | Add wire + state + parse_error + probe hooks |
| `src/meridian/lib/streaming/spawn_manager.py` | Pass tracer to `_drain_loop`, add to `SpawnSession`, add `get_tracer()`, close in cleanup |
| `src/meridian/lib/app/ws_endpoint.py` | Add tracer parameter to loops, add mapper + WS trace hooks |
| `src/meridian/cli/streaming_serve.py` | Create tracer when `--debug`, pass via config |
| `src/meridian/cli/app_cmd.py` | Accept `--debug` flag, propagate to SpawnManager |
| `src/meridian/cli/main.py` | Wire `--debug` CLI parameter |

## Edge Cases and Failure Modes

- **Tracer write fails (disk full, permissions):** `emit()` catches the exception, logs one `logger.warning`, sets `self._disabled = True`, and returns silently on all subsequent calls. The tracer never crashes the pipeline.
- **Serialization fails (non-serializable data):** Dict/list values in `data` are serialized via `json.dumps`; non-serializable values fall back to `repr()`. All serialization is inside the `try/except` in `emit()`.
- **First trace event fires before spawn dir exists:** `_ensure_open()` creates parent directories. The first `state_change(created→starting)` fires before adapters create the spawn dir — this is handled.
- **Concurrent emit() calls:** Protected by `threading.Lock`. The lock is uncontested in practice (one spawn = one event stream), but safe if drain_loop and fan_out race.
- **Large payloads:** Truncated at 4KB by default. The `bytes` field in data always reports the original size so you know truncation happened.
- **Tracer not closed (crash):** Python's GC and OS process exit will flush the file. No data loss beyond the current unflushed line.
- **drain_loop starts before SpawnSession registered:** Not a problem — the tracer is passed directly to `_drain_loop()` as a parameter, not looked up from SpawnSession.
- **debug.jsonl grows unbounded:** Acceptable for a debug mode — you only enable it when diagnosing problems. Future enhancement could add rotation.
- **OpenCode path probing noise:** Separated via `http_probe` event name; greppable out of traces.

## What This Does NOT Cover

- **Replay tooling.** A `meridian debug replay` command that reads `debug.jsonl` and pretty-prints the trace would be valuable but is a separate concern.
- **Performance profiling.** Debug mode captures protocol events, not timing/latency metrics. Profiling is a different tool.
- **Automatic protocol validation.** The tracer captures what happened; it doesn't assert correctness. A future layer could validate events against a schema, but that's additive.
