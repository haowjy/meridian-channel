# App Session Architecture — Overview

## Problem

`meridian app` launches a local web UI for interacting with agent spawns. The current implementation is a single-page app with no URL routing — everything lives on one page, one spawn at a time, with a hardcoded port and no server lifecycle management. This design adds URL-routable sessions, a dashboard, server lifecycle management, multi-repo support, and multi-tab support.

## Architecture

One server per machine, serving all repos — like Jupyter. The server is user-level, not repo-level.

```
┌─────────────────────────────────────────────────────────┐
│  Browser                                                │
│  ┌──────────────┐  ┌────────────────────────────────┐   │
│  │  Dashboard    │  │  Session View                  │   │
│  │  /            │  │  /s/<session_id>               │   │
│  │              │──▶│                                │   │
│  │  List + Create│  │  Thread + Composer + WS        │   │
│  │  (grouped by  │  │                                │   │
│  │   repo)       │  │                                │   │
│  └──────────────┘  └────────────────────────────────┘   │
│         │                       │                        │
│         │  wouter client-side routing                    │
└─────────┼───────────────────────┼────────────────────────┘
          │ REST                  │ REST + WS
┌─────────┼───────────────────────┼────────────────────────┐
│  FastAPI Server (one per machine)                        │
│         │                       │                        │
│  ┌──────▼───────────────────────▼──────┐                 │
│  │  Session API (/api/sessions/...)    │                 │
│  │  Thin layer: session_id → spawn_id  │                 │
│  │  Each session carries its repo_root │                 │
│  └──────┬──────────────────────────────┘                 │
│         │                                                │
│  ┌──────▼──────────────────────────────┐                 │
│  │  SpawnManager (multi-repo aware)    │                 │
│  │  No global state_root/repo_root     │                 │
│  │  Per-spawn paths from ConnectionCfg │                 │
│  └─────────────────────────────────────┘                 │
│                                                          │
│  ┌─────────────────────────────────────┐                 │
│  │  AppSessionRegistry                 │                 │
│  │  In-memory dict + ~/.meridian/app/  │                 │
│  │  sessions.jsonl on disk             │                 │
│  └─────────────────────────────────────┘                 │
│                                                          │
│  ┌─────────────────────────────────────┐                 │
│  │  Server Lifecycle                   │                 │
│  │  User-level lockfile + flock        │                 │
│  └─────────────────────────────────────┘                 │
└──────────────────────────────────────────────────────────┘
```

## URL Scheme

| URL | Purpose |
|-----|---------|
| `http://localhost:8420/` | Dashboard — list active sessions across all repos, create new spawns |
| `http://localhost:8420/s/<session_id>` | Session view — thread, composer, streaming |
| `http://localhost:8420/api/sessions` | REST: list/create sessions |
| `http://localhost:8420/api/sessions/<sid>` | REST: get/cancel one session |
| `http://localhost:8420/api/sessions/<sid>/ws` | WebSocket: stream events for session |
| `http://localhost:8420/api/health` | Health check (server discovery) |
| `http://localhost:8420/api/spawns/...` | Legacy spawn API (unchanged) |

Session IDs are random 8-char hex strings (e.g., `a7f3b2c1`). They are globally unique and not derived from spawn IDs.

## Key Concepts

**Session = URL-addressable spawn alias.** A session is a thin mapping from a random, URL-safe ID to a spawn_id plus its repo context. Every session has exactly one spawn. The session exists so that URLs are shareable, bookmarkable, and don't expose sequential spawn IDs. Each session carries a `repo_root` so the server knows which repo's `.meridian/` holds the spawn artifacts.

**One server per machine.** The entire machine gets at most one `meridian app` server. Running `meridian app` from any repo either starts the global server or opens the browser to the existing instance. There is no per-repo server discovery — just one lockfile at `~/.meridian/app/server.json`. This is the Jupyter model: a single dashboard at localhost:8420 showing all agent sessions across all repos.

**Multi-repo sessions.** Each session carries a `repo_root` that identifies which repo it belongs to. Spawn artifacts (output.jsonl, inbound.jsonl, control.sock) stay in each repo's `.meridian/spawns/` directory, so `meridian spawn show` works per-repo as before. The dashboard groups sessions by repo.

**Sessions persist across server restarts.** Session-to-spawn mappings are written to `~/.meridian/app/sessions.jsonl` on creation. After a server restart, bookmarked session URLs still resolve — the `AppSessionRegistry` reloads from disk. For completed spawns, the session shows terminal status and metadata. Live streaming is only available for spawns started in the current server process (SpawnManager connections don't survive restarts). Full event replay from `output.jsonl` is a future enhancement.

**Frontend uses client-side routing.** The server serves `index.html` for both `/` and `/s/<session_id>` (SPA fallback). The `wouter` router in the browser parses the URL and renders the correct view. The dashboard and individual session views can be open in separate tabs. However, only one tab can receive live WebSocket events per session (existing SpawnManager subscriber exclusivity). A second tab opening the same session URL sees session metadata but cannot stream live events.

## Component Design Docs

| Doc | Covers |
|-----|--------|
| [server-lifecycle.md](server-lifecycle.md) | User-level lockfile, port selection, start/stop, flock |
| [session-registry.md](session-registry.md) | Session ID generation, multi-repo storage format, session API endpoints |
| [frontend-routing.md](frontend-routing.md) | Client-side routing, component restructuring, multi-repo dashboard design |

## What Changes

- **SpawnManager** (`src/meridian/lib/streaming/spawn_manager.py`) — removes global `state_root` and `repo_root` constructor params. Each spawn derives its own state_root from the `ConnectionConfig.repo_root`. The `_spawn_dir()`, `_output_log_path()`, and `_inbound_log_path()` methods use per-spawn paths.
- **AppSessionRegistry** — moves from `.meridian/app/sessions.jsonl` to `~/.meridian/app/sessions.jsonl`. Session entries include `repo_root`.
- **Server lifecycle** — moves from per-repo lockfile (`.meridian/app/server.json`) to user-level lockfile (`~/.meridian/app/server.json`).
- **Session creation API** — `POST /api/sessions` accepts `repo_root` (or `cwd`) to identify which repo the spawn belongs to.
- **Dashboard** — groups sessions by repo.

## What Does NOT Change

- **Session ID format** — 8-char hex strings.
- **URL scheme** — `/`, `/s/<session_id>`, `/api/sessions/...`.
- **Frontend routing** — wouter, Dashboard + SessionView components.
- **WS event protocol** — AG-UI event format over WebSocket stays the same.
- **Harness connections** — no changes to connection lifecycle, drain loops, or control sockets.
- **Spawn store** (`src/meridian/lib/state/spawn_store.py`) — unchanged. Sessions reference spawn IDs but don't modify spawn state.
- **Legacy spawn API** — existing `/api/spawns/...` endpoints remain functional.
- **Shutdown draining** — flock serialization and draining flag work the same way, just at user level.

## Future: `--host 0.0.0.0` Auth

When `--host` support is added later, authentication will use a token query parameter (`?token=abc123`) that sets a cookie on first visit. The URL structure (`/`, `/s/<session_id>`, `/api/...`) stays identical. The token validation adds a middleware layer — no routing changes needed.

The session API already uses random IDs that aren't guessable, which is a prerequisite for the auth model. The health endpoint will need to be excluded from auth (or use a separate auth mechanism) so discovery probes can reach it.
