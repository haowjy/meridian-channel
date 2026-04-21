# App

REST server layer that exposes spawn management as an HTTP API. Thin wrapper — delegates to the same launch and state machinery the CLI uses. Exists so external callers (IDEs, scripts, future UIs) can trigger spawns without shelling out.

## Module Map

```
src/meridian/lib/app/
└── server.py     — FastAPI application, spawn manager, lifecycle endpoints
```

## server.py — REST App Server

FastAPI application. Two concerns: request routing and spawn lifecycle management.

### Spawn Manager

Internal object holding active spawn state. Not a persistent store — purely in-memory for the lifetime of the server process. Persistent state goes to `.meridian/` via the normal state layer.

### SPEC_ONLY Launch Intent

The app server uses `LaunchIntent.SPEC_ONLY` when calling the launch factory:

```python
spec = launch_factory(intent=LaunchIntent.SPEC_ONLY, ...)
```

`SPEC_ONLY` builds the full launch spec (command args, env, harness config) but does not execute. The server then manages process lifecycle itself — allows HTTP response streaming, cancellation, and request-scoped cleanup that the standard blocking launcher doesn't support.

Contrast with CLI path: `LaunchIntent.EXECUTE` — build spec + run to completion in one call. See [launch](../launch/overview.md) for intent semantics.

### Output Routing

Server spawns use `MemorySink` (an `OutputSink` implementation from [core](../core/overview.md)) to capture output in-process rather than writing to `output.jsonl`. This lets the HTTP response stream events in real time without a separate file read loop.

### Endpoints

- `POST /spawn` — create and start a spawn
- `GET /spawn/{id}` — status and report
- `DELETE /spawn/{id}` — cancel
- `GET /spawn/{id}/stream` — SSE event stream of spawn output

### Why a Server at All

CLI spawns are fire-and-forget with blocking wait. The server enables: non-blocking invocation from async callers, SSE streaming to browser or IDE clients, and programmatic cancellation. The implementation stays thin because the hard logic lives in launch, state, and harness layers — the server just routes HTTP to those.
