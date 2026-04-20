# Session Registry

## Purpose

A session remains a metadata alias over a spawn. The registry maps a stable app-facing identifier to `(project_key, spawn_id, repo_root, work_id)` so the UI can keep durable references while runtime state stays spawn-keyed.

This keeps the original design intent:

- Spawn runtime state is keyed by project + spawn.
- Session aliases are app metadata only.
- Session aliases do not create new runtime storage boundaries.

## Canonical API Direction

The canonical backend surface is spawn-first (`../backend-gaps.md`). Public endpoints must use `/api/spawns*`, not `/api/sessions*`.

### Canonical endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/spawns?work_id=&status=&agent=&limit=&cursor=` | List for Sessions mode |
| `GET` | `/api/spawns/{spawn_id}` | Spawn/session detail |
| `POST` | `/api/spawns` | Create spawn |
| `POST` | `/api/spawns/{spawn_id}/cancel` | Cancel |
| `POST` | `/api/spawns/{spawn_id}/fork` | Fork |
| `POST` | `/api/spawns/{spawn_id}/archive` | Archive |
| `GET` | `/api/spawns/{spawn_id}/events?since=&tail=` | Activity/event feed |
| `GET` | `/api/spawns/stats?work_id=` | Aggregated counters |
| `GET` | `/api/stream` (SSE) or `WS /api/stream` | Multiplexed live updates |

### Removed from canonical direction

These legacy paths are stale in this design package and must not be used for new implementation:

- `POST /api/sessions`
- `GET /api/sessions`
- `GET /api/sessions/{session_id}`
- `PATCH /api/sessions/{session_id}`
- `DELETE /api/sessions/{session_id}`
- `POST /api/sessions/{session_id}/inject`
- `WS /api/sessions/{session_id}/ws`

## Storage

### Session registry file

`~/.meridian/app/sessions.jsonl` remains valid as app metadata:

```json
{"session_id": "a7f3b2c1", "project_key": "3f8a2b1c9d4e", "spawn_id": "p42", "repo_root": "/home/user/project-alpha", "work_id": "auth-middleware", "harness": "claude", "model": "claude-opus-4-6", "created_at": "2026-04-09T14:30:00Z"}
```

Fields:

- `session_id`: opaque app alias.
- `project_key`: project namespace for spawn runtime state.
- `spawn_id`: canonical runtime identity within the project.
- `repo_root`: workspace root for display and launch context.
- `work_id`: nullable work attachment.
- `harness`, `model`, `created_at`: denormalized listing metadata.

### Runtime boundary (unchanged)

```text
~/.meridian/projects/<project_key>/spawns/<spawn_id>/    # runtime state
~/.meridian/projects/<project_key>/sessions/<session_id>/ # never used
```

## How session aliases fit spawn APIs

Session aliases are an internal index and optional UI convenience. API requests operate on `spawn_id`.

### Create

Request:

```json
{
  "agent": "dev-orchestrator",
  "model": "claude-opus-4-6",
  "work_id": "auth-middleware",
  "prompt": "Implement JWT auth middleware",
  "reference_files": ["design/overview.md"]
}
```

Endpoint: `POST /api/spawns`

Response:

```json
{
  "spawn_id": "p42",
  "chat_id": "chat_abc123",
  "status": "queued"
}
```

Server-side behavior may create/update a session-alias entry, but the public contract returns `spawn_id`.

### List

Endpoint: `GET /api/spawns?work_id=auth-middleware&status=running`

Example response:

```json
[
  {
    "spawn_id": "p42",
    "work_id": "auth-middleware",
    "status": "running",
    "agent": "dev-orchestrator",
    "model": "claude-opus-4-6",
    "created_at": "2026-04-09T14:30:00Z"
  }
]
```

### Detail

Endpoint: `GET /api/spawns/p42`

Example response:

```json
{
  "spawn_id": "p42",
  "chat_id": "chat_abc123",
  "work_id": "auth-middleware",
  "status": "running",
  "agent": "dev-orchestrator",
  "model": "claude-opus-4-6",
  "created_at": "2026-04-09T14:30:00Z"
}
```

## Lifecycle

1. Client creates via `POST /api/spawns`.
2. Runtime allocates `spawn_id` under project-scoped state.
3. App may record/update session alias metadata in `sessions.jsonl`.
4. UI streams updates from `/api/stream` and/or per-spawn event endpoints.
5. Terminal spawns remain queryable via `/api/spawns/{spawn_id}`.

## Decision

Keep the session-registry concept as internal metadata. Align all implementation-facing API examples and contracts to `/api/spawns*` and the three-mode UI direction.
