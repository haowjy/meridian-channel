# Server Lifecycle

## One Server Per Machine

The entire machine gets at most one `meridian app` server process. The server binds to a port, serves the web UI, and manages spawn connections across all repos. Any `meridian app` invocation from any repo either starts the global server or opens the browser to the existing instance.

This is the Jupyter model — one dashboard at localhost:8420 showing everything.

## State Files

### User-level lockfile: `~/.meridian/app/server.json`

Written atomically on server start, deleted on clean shutdown. Contains everything needed to reconnect to or validate the running server.

```json
{
  "pid": 12345,
  "port": 8420,
  "host": "127.0.0.1",
  "started_at": "2026-04-09T14:30:00Z"
}
```

This file answers: "is there already a server running on this machine, and how do I reach it?"

No `repo_root` field — the server is not scoped to any single repo. Sessions carry their own repo context.

### No server registry directory

With a single-server model, the `~/.meridian/app/servers/` directory from the per-repo design is unnecessary. There is at most one server, tracked by one lockfile. `meridian app list` reads the single lockfile.

## Startup Flow (`meridian app`)

The entire startup flow is serialized under a file lock (`~/.meridian/app/server.flock`) to prevent two concurrent `meridian app` invocations from racing. The lock is held from step 1 through step 5 (server bind), then released — the running server doesn't hold the lock after startup completes.

```
0. Ensure ~/.meridian/app/ directory exists
1. Acquire flock on ~/.meridian/app/server.flock (blocking, with 10s timeout)
2. Read ~/.meridian/app/server.json
   ├── File exists → validate server
   │   ├── PID alive AND health check succeeds
   │   │   → Release flock
   │   │   → Print "Server already running at http://host:port"
   │   │   → Open browser to existing URL (unless --no-browser)
   │   │   → Exit 0
   │   ├── PID alive AND health check fails (server starting up)
   │   │   → Release flock
   │   │   → Print "Server is starting at http://host:port"
   │   │   → Open browser to lockfile URL (unless --no-browser)
   │   │   → Exit 0
   │   └── PID dead
   │       → Delete stale lockfile
   │       → Continue to step 3
   └── File missing → continue to step 3
3. Select port (bind-and-hold: see Port Selection below)
4. Write lockfile (~/.meridian/app/server.json) with actual bound port
5. Release startup flock
6. Start uvicorn server (using the pre-bound socket)
7. Open browser (unless --no-browser)
```

If flock acquisition times out (10 seconds), print an error suggesting another `meridian app` instance is starting and exit.

### CLI Context — `repo_root` from `cwd`

When `meridian app` is invoked from a repo directory, the server stores no reference to that repo — the server is repo-agnostic. The CLI derives the invoking repo's root (for the `--open` use case: opening the browser to the dashboard, optionally filtered to sessions for this repo), but the server itself serves all repos equally.

When creating a spawn from the CLI (e.g., `meridian app spawn --prompt "..."`) the CLI determines the repo_root from the current directory and passes it to `POST /api/sessions` as the `repo_root` field.

### Stale Server Detection

A lockfile is stale if and only if the PID is dead (`os.kill(pid, 0)` raises `ProcessLookupError`). If the PID is alive, the server is considered running even if the health check fails — the server may be in the startup window between lockfile write and uvicorn readiness. This prevents a race where a second invocation deletes a legitimate lockfile during the first server's startup.

### Port Selection — Bind-and-Hold

To eliminate the race between port probing and uvicorn binding, the startup flow binds a TCP socket and holds it open through lockfile creation:

```python
def bind_server_socket(host: str, port: int | None, start: int = 8420, count: int = 10) -> socket.socket:
    """Bind and return a listening socket. Caller owns the socket."""
    if port is not None:
        # Explicit --port: bind exactly, fail on error
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        return sock
    # Auto-port: probe range
    for p in range(start, start + count):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, p))
            return sock
        except OSError:
            sock.close()
            continue
    raise RuntimeError(f"No available port in range {start}-{start + count - 1}")
```

The bound socket's port is read via `sock.getsockname()[1]` and written to the lockfile. The socket is then passed to uvicorn as a file descriptor (via `uvicorn.Config(fd=sock.fileno())`), so there is no window where the port is unowned. If uvicorn startup fails, the socket is closed and the lockfile is cleaned up.

## Shutdown Flow

### Clean shutdown (Ctrl-C / SIGTERM)

```
1. uvicorn receives signal
2. FastAPI lifespan __aexit__ fires
3. Set draining flag — reject new POST /api/sessions with 503
4. Wait for in-flight counter to reach 0 (with 10s timeout)
5. SpawnManager.shutdown() stops all active spawn connections
6. Delete ~/.meridian/app/server.json
7. Process exits
```

**Draining mechanism:** An `asyncio.Event` (draining flag) and an `int` counter (in-flight creates). `POST /api/sessions` checks the draining flag first (returns 503 if set). If not draining, it increments the counter before starting spawn creation and decrements it when creation completes (success or failure, via try/finally). Shutdown sets the draining flag, then waits for the counter to reach 0 before calling `SpawnManager.shutdown()`. The 10s timeout is a safety bound — if a create is truly stuck, shutdown proceeds anyway and logs a warning.

### Crash (SIGKILL / OOM / power loss)

The lockfile remains on disk. Next startup detects and cleans it via the PID-alive check in step 2 of the startup flow (see "Stale Server Detection" above). This is crash-only design — recovery is startup behavior.

## Server Discovery (`meridian app list`)

With a single-server model, discovery is simple:

```
1. Read ~/.meridian/app/server.json
   ├── File missing → "No server running"
   └── File exists → validate
       ├── PID dead → stale, delete file, print "No server running"
       └── PID alive → server is running
           - Optionally try GET http://host:port/api/health for status info
           - Print server info:
             PORT   URL                        STATUS    SESSIONS
             8420   http://127.0.0.1:8420     ready     5 active across 3 repos
```

## Server Stop (`meridian app stop`)

```
1. Read ~/.meridian/app/server.json
   ├── File missing → print "No server running", exit 1
   └── File exists → validate
       ├── PID dead → delete stale lockfile, print "No server running", exit 1
       └── PID alive → proceed
2. Send SIGTERM to server PID
3. Wait up to 5 seconds for process to exit
4. If still alive after 5s → send SIGKILL
5. Clean up lockfile if still present
```

No `--repo` flag needed — there's only one server.

## Health Endpoint

`GET /api/health` returns server identity and status:

```json
{
  "status": "ok",
  "port": 8420,
  "host": "127.0.0.1",
  "pid": 12345,
  "active_sessions": 5,
  "active_spawns": 3,
  "repos": ["project-alpha", "project-beta", "lib-core"],
  "uptime_secs": 123.4
}
```

No `repo_root` or `repo_name` — the server is not scoped to a repo. The `repos` field is a convenience listing derived from active sessions.

This endpoint is unauthenticated (even when `--host` auth is added later) so that discovery probes can reach it.

## Edge Cases

**Two terminals run `meridian app` simultaneously.** The startup flock at `~/.meridian/app/server.flock` serializes them. The first invocation acquires the lock, binds the port, writes the lockfile, and releases the lock. The second invocation acquires the lock, finds the lockfile, validates the running server, and opens the browser to the existing instance.

**Server crashes while spawns are running.** Spawn state is already persisted to each repo's `output.jsonl` and `spawns.jsonl` by the drain loop. On next server start, spawn stores in individual repos show them in their last recorded state. Active WebSocket connections from the browser break — the frontend shows "disconnected" status.

**User deletes `~/.meridian/app/` while server is running.** The server continues running with in-memory state. On next `meridian app` from any terminal, the missing lockfile causes a new server to start on the next available port. The old server is orphaned until killed. This is an edge case that doesn't need special handling — deleting state files while the process is running is user error.

**Lockfile points to wrong port (manual edit or corruption).** PID is still alive (the server is running, just on a different port than the lockfile claims). The second invocation sees PID-alive, treats the server as running, and opens the browser to the lockfile's URL (which won't work). The user sees a broken page and can `meridian app stop` + restart. This is a manual-edit-of-state-files scenario that doesn't warrant special handling.

**Repo is deleted while sessions reference it.** The session entry still has the `repo_root` path, but the directory (and its `.meridian/`) no longer exists. The `GET /api/sessions` endpoint handles this gracefully: the session appears in the list with a "repo unavailable" status indicator, and spawn store lookups for that repo fail with a clear error. The session entry remains in the registry (it's append-only); the frontend can filter or dim unavailable sessions.

**Two spawns from different repos have the same spawn_id.** This is expected — spawn IDs (e.g., `p1`, `p2`) are repo-scoped, not globally unique. The SpawnManager uses `(repo_root, spawn_id)` as the compound key (see SpawnManager section in the overview). Session IDs are globally unique and serve as the unambiguous external identifier.

## File Layout

```
~/.meridian/
  app/
    server.json           # Server lockfile (runtime only)
    server.flock          # Startup serialization flock (runtime only)
    sessions.jsonl        # Session registry — all repos (see session-registry.md)

<repo>/.meridian/
  spawns/
    <spawn_id>/
      output.jsonl        # Spawn event log (per-repo, unchanged)
      inbound.jsonl       # Inbound control log (per-repo, unchanged)
      control.sock        # Control socket (per-repo, unchanged)
```

The `~/.meridian/app/` directory is created on first `meridian app` invocation. Each repo's `.meridian/spawns/` is untouched — spawn artifacts stay repo-local.
