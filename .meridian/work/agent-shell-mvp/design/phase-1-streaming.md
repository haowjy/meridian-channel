# Phase 1 — Bidirectional Streaming Foundation

Phase 1 delivers the universal bidirectional streaming layer. Every spawn — Claude Code, Codex, OpenCode — can stream inputs as well as outputs. This is the foundation that Phase 2 and 3 build on.

## Deliverables

1. **`HarnessConnection` implementations** for all three tier-1 harnesses (see [harness-abstraction.md](harness-abstraction.md))
2. **`SpawnManager`** — in-process registry of active bidirectional connections
3. **Control socket** — per-spawn Unix domain socket for cross-process `inject`
4. **`meridian spawn inject <spawn_id> "message"`** — CLI command for mid-turn injection
5. **Smoke tests** — per-harness manual smoke test guides

## SpawnManager

The `SpawnManager` is the central coordination point for all bidirectional spawns. It lives at `src/meridian/lib/streaming/spawn_manager.py`.

```python
class SpawnManager:
    """Registry of active bidirectional harness connections.

    Owns the lifecycle of HarnessConnection instances. Each bidirectional
    spawn gets one connection. The SpawnManager starts the connection,
    registers it, serves the control socket, and tears it down when the
    spawn finishes.
    """

    def __init__(self, state_root: Path, repo_root: Path):
        self._connections: dict[SpawnId, HarnessConnection] = {}
        self._control_servers: dict[SpawnId, asyncio.AbstractServer] = {}
        self._state_root = state_root
        self._repo_root = repo_root

    async def start_spawn(
        self,
        config: ConnectionConfig,
    ) -> HarnessConnection:
        """Launch a new bidirectional spawn.

        1. Resolves the connection class from config.harness_id
        2. Records the spawn in spawn_store (status: "running")
        3. Creates the HarnessConnection and calls start()
        4. Starts the control socket listener
        5. Registers the connection

        Returns the connection for the caller to iterate events from.
        """
        ...

    async def inject(self, spawn_id: SpawnId, message: str) -> InjectResult:
        """Send a user message to a running spawn.

        Returns InjectResult indicating success, or an error if the spawn
        is not found, not running, or the adapter rejected the message.
        """
        connection = self._connections.get(spawn_id)
        if connection is None:
            return InjectResult(success=False, error="spawn not found or not bidirectional")
        try:
            await connection.send_user_message(message)
            return InjectResult(success=True)
        except Exception as e:
            return InjectResult(success=False, error=str(e))

    async def interrupt(self, spawn_id: SpawnId) -> InjectResult:
        """Interrupt the current turn of a running spawn."""
        ...

    async def cancel(self, spawn_id: SpawnId) -> InjectResult:
        """Cancel a running spawn entirely."""
        ...

    async def get_connection(self, spawn_id: SpawnId) -> HarnessConnection | None:
        """Get the connection for a spawn, or None if not found."""
        return self._connections.get(spawn_id)

    async def stop_spawn(self, spawn_id: SpawnId) -> None:
        """Stop a spawn and clean up its resources."""
        ...

    async def shutdown(self) -> None:
        """Stop all spawns and clean up. Called on process exit."""
        ...
```

## Control Socket

Each bidirectional spawn gets a Unix domain socket at `.meridian/spawns/<spawn_id>/control.sock`. This enables cross-process injection — `meridian spawn inject` from another terminal connects to this socket.

```python
# src/meridian/lib/streaming/control_socket.py

class ControlSocketServer:
    """Unix domain socket listener for one spawn's control channel.

    Protocol: each connection sends one JSON message and receives one JSON response.

    Request:  {"type": "user_message", "text": "..."} | {"type": "interrupt"} | {"type": "cancel"}
    Response: {"ok": true} | {"ok": false, "error": "reason"}
    """

    def __init__(self, spawn_id: SpawnId, socket_path: Path, manager: SpawnManager):
        self._spawn_id = spawn_id
        self._socket_path = socket_path
        self._manager = manager
        self._server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        """Start listening on the Unix domain socket."""
        self._socket_path.parent.mkdir(parents=True, exist_ok=True)
        self._socket_path.unlink(missing_ok=True)
        self._server = await asyncio.start_unix_server(
            self._handle_client,
            path=str(self._socket_path),
        )

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle one control socket connection."""
        try:
            data = await asyncio.wait_for(reader.readline(), timeout=5.0)
            msg = json.loads(data)
            msg_type = msg.get("type")

            if msg_type == "user_message":
                result = await self._manager.inject(self._spawn_id, msg["text"])
            elif msg_type == "interrupt":
                result = await self._manager.interrupt(self._spawn_id)
            elif msg_type == "cancel":
                result = await self._manager.cancel(self._spawn_id)
            else:
                result = InjectResult(success=False, error=f"unknown message type: {msg_type}")

            response = {"ok": result.success}
            if not result.success:
                response["error"] = result.error
            writer.write(json.dumps(response).encode() + b"\n")
            await writer.drain()
        except Exception as e:
            writer.write(json.dumps({"ok": False, "error": str(e)}).encode() + b"\n")
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async def stop(self) -> None:
        """Stop the socket server and clean up the socket file."""
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
        self._socket_path.unlink(missing_ok=True)
```

### Socket path convention

```
.meridian/spawns/<spawn_id>/control.sock
```

This is within the existing per-spawn artifact directory, so cleanup happens naturally when the spawn's artifacts are cleaned up. The socket file is removed when the control server stops.

## `meridian spawn inject` CLI Command

```python
# src/meridian/cli/spawn_inject.py

async def inject_message(spawn_id: str, message: str) -> None:
    """Send a user message to a running bidirectional spawn.

    Connects to the spawn's control socket, sends the message, and
    prints the result.
    """
    socket_path = resolve_spawn_log_dir(repo_root, SpawnId(spawn_id)) / "control.sock"

    if not socket_path.exists():
        # Spawn exists but no control socket → not a bidirectional spawn
        print(f"Error: spawn {spawn_id} has no control socket (not a bidirectional spawn)")
        sys.exit(1)

    reader, writer = await asyncio.open_unix_connection(str(socket_path))
    try:
        request = json.dumps({"type": "user_message", "text": message}) + "\n"
        writer.write(request.encode())
        await writer.drain()

        response_data = await asyncio.wait_for(reader.readline(), timeout=10.0)
        response = json.loads(response_data)

        if response.get("ok"):
            print(f"Message delivered to spawn {spawn_id}")
        else:
            print(f"Error: {response.get('error', 'unknown error')}")
            sys.exit(1)
    finally:
        writer.close()
        await writer.wait_closed()
```

**CLI interface**:
```bash
meridian spawn inject <spawn_id> "reconsider the approach for auth middleware"
meridian spawn inject <spawn_id> --interrupt
meridian spawn inject <spawn_id> --cancel
```

## Integration With Existing Spawn Infrastructure

### Spawn state recording

Bidirectional spawns use the same `spawn_store` as fire-and-forget spawns:

```python
# In SpawnManager.start_spawn():
spawn_id = spawn_store.start_spawn(
    state_root,
    chat_id=chat_id,
    model=config.model,
    agent=config.agent,
    harness=str(config.harness_id),
    kind="bidirectional",           # New kind value
    prompt=config.prompt,
    execution_cwd=str(config.repo_root),
    launch_mode="bidirectional",    # New launch mode
    work_id=work_id,
    status="running",
)
```

The `kind="bidirectional"` and `launch_mode="bidirectional"` values distinguish these from fire-and-forget spawns in `meridian spawn list` and health checks.

### Artifact storage

Bidirectional spawns write to the same artifact directory:
- `.meridian/spawns/<spawn_id>/output.jsonl` — raw harness events (for replay/debugging)
- `.meridian/spawns/<spawn_id>/stderr.log` — harness stderr
- `.meridian/spawns/<spawn_id>/heartbeat` — liveness signal
- `.meridian/spawns/<spawn_id>/control.sock` — **new**: control socket
- `.meridian/spawns/<spawn_id>/connection.json` — **new**: connection metadata (harness, capabilities, transport details)

### Heartbeat

The `SpawnManager` maintains the heartbeat file for each active connection, using the existing `heartbeat_scope` from `launch/heartbeat.py`. Orphan detection (`meridian doctor`) works the same way.

## Refactoring Scope Against Existing Code

### What stays unchanged

| File | Why |
|---|---|
| `harness/claude.py` | Fire-and-forget adapter. `ClaudeAdapter.build_command()` still used for non-interactive spawns. |
| `harness/codex.py` | Same — fire-and-forget stays. |
| `harness/opencode.py` | Same. |
| `harness/adapter.py` | `SubprocessHarness` protocol unchanged. `HarnessCapabilities` extended (see below). |
| `harness/registry.py` | Unchanged — still resolves `SubprocessHarness` instances. |
| `launch/runner.py` | Unchanged — async subprocess execution for fire-and-forget spawns. |
| `launch/process.py` | Unchanged — primary interactive launch with PTY. |
| `launch/stream_capture.py` | Unchanged — stdout/stderr capture for fire-and-forget. |
| `state/spawn_store.py` | Extended with new `kind` and `launch_mode` values. |

### What's extended

**`harness/adapter.py`** — `HarnessCapabilities` gains new fields:

```python
class HarnessCapabilities(BaseModel):
    # ... existing fields ...
    supports_stream_events: bool = True
    supports_stdin_prompt: bool = False
    # ... etc ...

    # NEW: bidirectional connection support
    supports_bidirectional: bool = False
    mid_turn_injection: Literal["queue", "interrupt_restart", "http_post", "none"] = "none"
```

Each existing adapter (`ClaudeAdapter`, `CodexAdapter`, `OpenCodeAdapter`) gets `supports_bidirectional=True` and the appropriate `mid_turn_injection` value added to their `capabilities` property.

**`state/spawn_store.py`** — `start_spawn()` accepts `kind="bidirectional"` and `launch_mode="bidirectional"`. Minimal change — these are just string values in the JSONL record.

### What's new

| New file | Purpose |
|---|---|
| `harness/connections/__init__.py` | Connection registry |
| `harness/connections/base.py` | `HarnessConnection` ABC, `HarnessEvent`, `ConnectionConfig`, `ConnectionCapabilities` |
| `harness/connections/claude_ws.py` | `ClaudeConnection` — WS server adapter |
| `harness/connections/codex_ws.py` | `CodexConnection` — WS client adapter |
| `harness/connections/opencode_http.py` | `OpenCodeConnection` — HTTP adapter |
| `streaming/__init__.py` | Package init |
| `streaming/spawn_manager.py` | `SpawnManager` |
| `streaming/control_socket.py` | `ControlSocketServer` |
| `streaming/types.py` | `ControlMessage`, `InjectResult` |
| `cli/spawn_inject.py` | `meridian spawn inject` command |

### What's NOT touched

The entire `launch/` directory is untouched. The bidirectional path is a parallel code path, not a modification of the existing launch path. This is deliberate — the fire-and-forget path is battle-tested and powers all existing meridian spawns. Phase 1 adds a new path alongside it, not a replacement.

The existing `SubprocessHarness` adapters (`ClaudeAdapter`, `CodexAdapter`, `OpenCodeAdapter`) are not modified beyond adding the `supports_bidirectional` and `mid_turn_injection` capability flags. Their command-building, report extraction, and session management logic stays as-is.

## Phase 1 Gate: Smoke Tests

Each harness gets a smoke test guide (markdown) verifying the end-to-end bidirectional path. Format follows the `smoke-test` skill methodology.

### Claude Code smoke test

```
1. Start a bidirectional Claude spawn:
   meridian app  (or a test harness that starts SpawnManager directly)

2. In another terminal, verify the spawn is running:
   meridian spawn list  →  shows spawn with kind="bidirectional"

3. Inject a mid-turn message:
   meridian spawn inject <spawn_id> "What files have you read so far?"

4. Verify in the spawn's output.jsonl that:
   - The user message was delivered (a "user" type event appears)
   - Claude responded to the injected message (an "assistant" type event follows)

5. Inject an interrupt:
   meridian spawn inject <spawn_id> --interrupt

6. Verify the spawn handled the interrupt gracefully.
```

### Codex smoke test

Same structure, but verifying:
- `turn/steer` delivery (mid-turn) or `turn/start` (new turn)
- Codex responded to the injected message
- `turn/interrupt` works

### OpenCode smoke test

Same structure, but verifying:
- HTTP POST delivery to the session endpoint
- OpenCode processed the message and produced a response

## Implementation Notes

### Port allocation

Both Claude and Codex need a port for their WebSocket (Claude: our server port; Codex: Codex's server port). Use port 0 to let the OS auto-assign, then read the actual port from the socket info.

For Claude: `websockets.serve(handler, "127.0.0.1", 0)` → read `server.sockets[0].getsockname()[1]`
For Codex: let Codex choose its own port via `--listen ws://127.0.0.1:0`, then read the port from Codex's startup output.

### Subprocess management

The bidirectional path uses `asyncio.create_subprocess_exec()` (same as `runner.py`) but does NOT capture stdout/stderr via pipes in the same way. Instead:
- Claude: communication is over WS, not stdio. Stdout/stderr are captured to artifact files for debugging.
- Codex: communication is over WS (JSON-RPC). Same artifact capture pattern.
- OpenCode: communication is over HTTP. Same artifact capture pattern.

The subprocess is still managed with SIGTERM → timeout → SIGKILL shutdown, reusing the patterns from `launch/timeout.py`.

### Error propagation

If the harness subprocess dies unexpectedly:
1. The transport (WS or HTTP) raises an exception
2. The `HarnessConnection.events()` iterator yields a final error event and completes
3. The `SpawnManager` marks the spawn as failed in `spawn_store`
4. The control socket server is shut down
5. Phase 2 (if running) sends a `RUN_ERROR` AG-UI event to the connected client

### Graceful shutdown

When `SpawnManager.shutdown()` is called (process exit):
1. Send `cancel` to each active connection
2. Wait for each harness subprocess to exit (with timeout)
3. Close all control sockets
4. Finalize spawn states in `spawn_store`
