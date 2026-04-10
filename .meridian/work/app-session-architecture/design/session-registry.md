# Session Registry

## What a Session Is

A session is a URL-addressable alias for a spawn in a specific repo. It maps a random, globally unique ID to a `(repo_root, spawn_id)` pair. This indirection exists because:

1. **Spawn IDs are sequential and predictable** (`p1`, `p2`, ...) — unsuitable for URLs that might be shared or bookmarked.
2. **Spawn IDs are only unique within a repo** — with a single server handling multiple repos, session IDs must be globally unambiguous across all repos.
3. **URLs should be opaque** — exposing spawn IDs in URLs leaks information about spawn count and ordering.

Every session maps to exactly one spawn in one repo. A spawn may have zero or one sessions (spawns created through the CLI have no session; spawns created through the app always have one).

## Session ID Format

8-character lowercase hexadecimal string, generated via `secrets.token_hex(4)`.

Examples: `a7f3b2c1`, `0e9d4f8a`, `b3c71e50`

This gives 2^32 (~4.3 billion) possible IDs — far more than a local dev tool will ever generate. The format is URL-safe, case-insensitive, and trivially generated without external dependencies.

## Storage

### On-disk: `~/.meridian/app/sessions.jsonl`

User-level, append-only JSONL file. Each line records one session creation:

```json
{"session_id": "a7f3b2c1", "spawn_id": "p42", "repo_root": "/home/user/project-alpha", "harness": "claude", "model": "claude-opus-4-6", "created_at": "2026-04-09T14:30:00Z"}
```

Fields:
- `session_id` — the random session ID
- `spawn_id` — the spawn this session maps to (repo-scoped)
- `repo_root` — absolute path to the repo this spawn belongs to
- `harness` — harness used (denormalized for fast listing)
- `model` — model used, if known (denormalized)
- `created_at` — ISO 8601 timestamp

The `repo_root` field is critical — it's what allows the server to find spawn artifacts in the correct repo's `.meridian/spawns/` directory, and it's what the dashboard uses to group sessions by repo.

This file is the source of truth for session-to-spawn mappings. It's loaded on server start to rebuild the in-memory lookup.

No update or delete events are needed. Sessions are immutable — the spawn behind them has its own lifecycle tracked in each repo's `spawns.jsonl`.

### In-memory: `AppSessionRegistry`

```python
@dataclass
class AppSessionEntry:
    session_id: str
    spawn_id: SpawnId
    repo_root: Path
    harness: str
    model: str | None
    created_at: str

class AppSessionRegistry:
    def __init__(self, app_state_dir: Path):
        self._app_state_dir = app_state_dir  # ~/.meridian/app/
        self._sessions: dict[str, AppSessionEntry] = {}  # session_id → entry
        self._spawn_to_session: dict[tuple[Path, SpawnId], str] = {}  # (repo_root, spawn_id) → session_id
        self._load()
    
    def _load(self) -> None:
        """Load session mappings from ~/.meridian/app/sessions.jsonl"""
    
    def create(self, spawn_id: SpawnId, repo_root: Path, harness: str, model: str | None) -> str:
        """Create a new session, persist it, return session_id."""
    
    def get(self, session_id: str) -> AppSessionEntry | None:
        """Look up a session by ID."""
    
    def get_by_spawn(self, repo_root: Path, spawn_id: SpawnId) -> AppSessionEntry | None:
        """Look up a session by its repo + spawn ID."""
    
    def list_all(self) -> list[AppSessionEntry]:
        """Return all sessions, ordered by creation time."""
    
    def list_by_repo(self, repo_root: Path) -> list[AppSessionEntry]:
        """Return sessions for one repo, ordered by creation time."""
    
    def repos(self) -> list[Path]:
        """Return distinct repo_roots across all sessions."""
```

Key changes from the per-repo design:
- Constructor takes `app_state_dir` (user-level `~/.meridian/app/`) instead of a per-repo `state_root`.
- `_spawn_to_session` is keyed by `(repo_root, spawn_id)` tuple since spawn IDs are only unique within a repo.
- `get_by_spawn()` requires `repo_root` in addition to `spawn_id`.
- `list_by_repo()` and `repos()` added for dashboard grouping.

The registry is instantiated once per server and shared across all request handlers via `app.state`. The class lives in `src/meridian/lib/app/session_registry.py` — it's an app-layer concern (URL-addressable aliases), not a state-layer concern like `spawn_store`.

### Collision Handling

If `secrets.token_hex(4)` generates a duplicate (astronomically unlikely), the `create()` method retries with a new random ID, up to 5 attempts. On failure (implies a broken random source), it raises an error.

## Session API

The session API is the primary interface for the frontend. It wraps the existing spawn infrastructure with session-level addressing.

### `POST /api/sessions` — Create Session

Request:
```json
{
  "harness": "claude",
  "prompt": "Implement the auth middleware...",
  "model": "claude-opus-4-6",
  "agent": null,
  "repo_root": "/home/user/project-alpha"
}
```

The `repo_root` field identifies which repo the spawn belongs to. It is **required** — the server has no default repo. When the CLI invokes this endpoint, it resolves `repo_root` from the current working directory. The frontend includes `repo_root` from a repo selector or from the repo context of the current dashboard view.

Validation:
- `repo_root` must be an absolute path
- `repo_root` must exist as a directory
- `repo_root/.meridian/` must exist (it's a meridian-enabled repo)

Response:
```json
{
  "session_id": "a7f3b2c1",
  "spawn_id": "p42",
  "repo_root": "/home/user/project-alpha",
  "harness": "claude",
  "state": "connected",
  "capabilities": {
    "midTurnInjection": "queue",
    "supportsSteer": true,
    "supportsInterrupt": true,
    "supportsCancel": true,
    "runtimeModelSwitch": false,
    "structuredReasoning": true
  }
}
```

Internally:
1. Check draining flag — reject with 503 if server is shutting down
2. Derive `state_root` from `repo_root` (i.e., `repo_root / ".meridian"`)
3. Create spawn via `reserve_spawn_id()` using the repo's state_root + `SpawnManager.start_spawn()`
4. Create session via `AppSessionRegistry.create(spawn_id, repo_root, ...)`
5. Return combined response with session_id

**Failure compensation:** If step 4 fails (session JSONL write error), the spawn from step 3 is already running with no session mapping. The handler calls `SpawnManager.stop_spawn()` to cancel the orphaned spawn and returns 500 to the client. This ensures no spawn runs without a session URL to reach it through.

### `GET /api/sessions` — List Sessions

Query params:
- `repo_root` (optional) — filter to sessions from one repo

Response:
```json
[
  {
    "session_id": "a7f3b2c1",
    "spawn_id": "p42",
    "repo_root": "/home/user/project-alpha",
    "repo_name": "project-alpha",
    "harness": "claude",
    "model": "claude-opus-4-6",
    "status": "running",
    "created_at": "2026-04-09T14:30:00Z",
    "prompt": "Implement the auth middleware..."
  },
  {
    "session_id": "0e9d4f8a",
    "spawn_id": "p41",
    "repo_root": "/home/user/project-beta",
    "repo_name": "project-beta",
    "harness": "codex",
    "model": null,
    "status": "succeeded",
    "created_at": "2026-04-09T14:20:00Z",
    "prompt": "Fix the login bug..."
  }
]
```

Joins session registry data with spawn store data. The `status` field comes from the spawn record (via `spawn_store.get_spawn()` called against the session's repo-specific state_root). The `repo_name` is derived from the last path component of `repo_root`. The `prompt` field is truncated if long.

Sessions are returned in reverse chronological order (newest first).

**Repo unavailability:** If a session's `repo_root` no longer exists (repo deleted or unmounted), the session still appears in the list with `"status": "repo_unavailable"`. The spawn store lookup is skipped for unavailable repos.

### `GET /api/sessions/{session_id}` — Get Session

Response:
```json
{
  "session_id": "a7f3b2c1",
  "spawn_id": "p42",
  "repo_root": "/home/user/project-alpha",
  "repo_name": "project-alpha",
  "harness": "claude",
  "model": "claude-opus-4-6",
  "status": "running",
  "created_at": "2026-04-09T14:30:00Z",
  "prompt": "Implement the auth middleware...",
  "capabilities": { ... }
}
```

If the spawn is active, capabilities are populated from the live connection. If the spawn is completed, capabilities may be null.

Returns 404 if session_id is not found.

### `DELETE /api/sessions/{session_id}` — Cancel Session

Cancels the spawn behind the session. Delegates to `SpawnManager.cancel()`.

Returns `{"ok": true}` on success, 404 if session not found, 400 if spawn is already terminated.

### `POST /api/sessions/{session_id}/inject` — Inject Message

Request:
```json
{"text": "Try a different approach..."}
```

Delegates to `SpawnManager.inject()` using the session's spawn_id.

### `WS /api/sessions/{session_id}/ws` — Stream Events

WebSocket endpoint. Resolves session_id → spawn_id, then delegates to the existing `spawn_websocket()` function.

The WebSocket protocol (AG-UI events, control messages) is identical to the existing `/api/spawns/{spawn_id}/ws` endpoint. The only difference is the addressing — session_id instead of spawn_id.

Origin validation and subscriber management work the same way.

## SpawnManager — Multi-Repo Aware

The SpawnManager changes to support spawns from multiple repos in a single server process.

### Constructor Change

```python
# Before (per-repo):
class SpawnManager:
    def __init__(self, state_root: Path, repo_root: Path):
        self._state_root = state_root
        self._repo_root = repo_root

# After (multi-repo):
class SpawnManager:
    def __init__(self) -> None:
        self._sessions: dict[SpawnId, SpawnSession] = {}
```

The constructor takes no path arguments. Each spawn gets its paths from the `ConnectionConfig` passed to `start_spawn()`.

### Per-Spawn Path Resolution

`SpawnSession` gains a `state_root` field derived from the spawn's `ConnectionConfig.repo_root`:

```python
@dataclass
class SpawnSession:
    connection: HarnessConnection
    drain_task: asyncio.Task[None]
    subscriber: asyncio.Queue[HarnessEvent | None] | None
    control_server: ControlSocketServer
    started_monotonic: float
    state_root: Path      # <repo>/.meridian/ — per-spawn
    repo_root: Path       # <repo>/ — per-spawn
```

The path helper methods become per-spawn instead of using global state:

```python
# Before:
def _spawn_dir(self, spawn_id: SpawnId) -> Path:
    return self._state_root / "spawns" / str(spawn_id)

# After:
def _spawn_dir(self, spawn_id: SpawnId) -> Path:
    session = self._sessions[spawn_id]
    return session.state_root / "spawns" / str(spawn_id)
```

Same pattern for `_output_log_path()` and `_inbound_log_path()`.

### spawn_store calls

The `_finalize_spawn()` and `_cleanup_completed_session()` methods call `spawn_store.finalize_spawn(state_root, ...)`. In the multi-repo model, they use the session's per-spawn `state_root` instead of a global one:

```python
def _finalize_spawn(self, spawn_id: SpawnId, *, session: SpawnSession, ...):
    spawn_store.finalize_spawn(
        session.state_root,  # was self._state_root
        spawn_id, ...
    )
```

### server.py changes

The `create_app()` function currently takes a `SpawnManager` and closes over `state_root` and `repo_root` from it. In the multi-repo model:

- `SpawnManager()` is constructed with no arguments
- `reserve_spawn_id()` derives `state_root` from the request's `repo_root`
- `ConnectionConfig.repo_root` comes from the request, not from a global

### Spawn ID Uniqueness

Spawn IDs (e.g., `p1`, `p2`) are only unique within a repo — each repo's `spawns.jsonl` has its own counter. With multiple repos in one server, two concurrent spawns could have the same `spawn_id` string.

The SpawnManager's `_sessions` dict currently uses `SpawnId` as the key. This must change to a compound key that includes repo identity. Two options:

1. **Tuple key:** `_sessions: dict[tuple[Path, SpawnId], SpawnSession]` — explicit but changes all lookup call sites.
2. **Qualified spawn ID:** Generate a server-scoped unique key (e.g., hash of `repo_root + spawn_id`) that maps cleanly to a string key.

**Decision:** Use a tuple key `(repo_root, spawn_id)` as the internal compound key. This is explicit, type-safe, and avoids introducing a new ID format. All SpawnManager methods that take a `spawn_id` now also take a `repo_root`. The session layer resolves the session_id to both values, so external callers (API handlers) always go through session → (repo_root, spawn_id).

A type alias keeps call sites readable:

```python
SpawnKey = tuple[Path, SpawnId]
```

## Session Lifecycle

### Creation

A session is created when the user clicks "Start Spawn" on the dashboard. The `POST /api/sessions` endpoint creates both the spawn and the session atomically. The `repo_root` is part of the request.

### Active

While the spawn is running, the session is "active." The browser connects via WebSocket and streams events in real-time. Multiple browser tabs can navigate to the same session URL, but only one tab gets the live WebSocket stream (existing subscriber-exclusivity from `SpawnManager.subscribe()`).

### Completed

When the spawn finishes (succeeded, failed, cancelled), the session remains navigable. On page load:

1. `GET /api/sessions/{session_id}` returns the session with terminal status.
2. The frontend shows the terminal state without attempting WebSocket connection.
3. Future enhancement: replay events from `output.jsonl` for completed sessions.

### Server Restart

After a server restart, the `AppSessionRegistry` reloads from `~/.meridian/app/sessions.jsonl`. Bookmarked session URLs continue to work:

- If the spawn is still "running" in spawn store (stale — server crashed), the session shows the last known state.
- If the spawn is terminal, the session shows the terminal state.
- Live streaming is only available for spawns started in the current server process (they need active `SpawnManager` sessions).

## Boundary: What Sessions Don't Do

- Sessions don't replace spawn_id as the internal identifier — SpawnManager, spawn_store, and all internal systems continue to use spawn_id (plus repo_root as disambiguation).
- Sessions don't create a new state store — spawn state lives in each repo's `spawns.jsonl`, session state is a thin mapping on top at the user level.
- Sessions don't support "connecting to an existing CLI spawn" in this version. That's a future feature that would add a `POST /api/sessions/attach` endpoint.
