# Backend Gaps — API Endpoints the Frontend Needs

**Target server:** `src/meridian/lib/app/server.py` (FastAPI, port 7676).

This document identifies the endpoint surface required by the three-mode UI. Where an endpoint likely already exists it is noted as "assumed present" and the frontend should verify via the running server before implementing. Genuine gaps (new endpoints) are marked **NEW**.

> Verification note: the frontend-designer spawn runs sandboxed and could not read `server.py` directly. The @frontend-coder must confirm the existing surface (`curl http://127.0.0.1:7676/openapi.json` is the fastest path) and map the "assumed present" rows to real endpoints before building.

---

## 1. Sessions / spawns

| Method | Path | Purpose | Status |
|---|---|---|---|
| `GET` | `/api/spawns?work_id=&status=&agent=&limit=&cursor=` | Paginated list for Sessions mode, with filters. | assumed present; **NEW** if no filter/cursor support |
| `GET` | `/api/spawns/{spawn_id}` | Full detail: params, state, timestamps, artifacts index. | assumed present |
| `POST` | `/api/spawns` | Create a new spawn (mirror of `meridian spawn`). Body: `{ agent, model?, work_id?, prompt, reference_files[], template_vars? }`. Returns `{ spawn_id, chat_id, status }`. | assumed present |
| `POST` | `/api/spawns/{spawn_id}/cancel` | Cancel a running/queued spawn. | assumed present |
| `POST` | `/api/spawns/{spawn_id}/fork` | Fork a spawn at the current tail or at a specific message. Body: `{ from_message_id? }`. | **NEW** if not present |
| `POST` | `/api/spawns/{spawn_id}/archive` | Soft-hide a terminal spawn. | **NEW** |
| `GET` | `/api/spawns/{spawn_id}/events?since=&tail=` | Server-sent events of activity stream for the Sessions mode sparkline + live status dot. | **NEW** if only WS exists |
| `GET` | `/api/spawns/stats?work_id=` | Aggregated counts for status bar (running/queued/done/failed, last 24 h). | **NEW** |

**Live updates.** Sessions mode needs a single multiplexed stream (WS or SSE) pushing spawn state transitions and per-spawn activity tick counts so the whole dashboard stays live without polling.

- `WS /api/stream` or `GET /api/stream` (SSE) — event types: `spawn.created`, `spawn.state_changed`, `spawn.finalized`, `spawn.activity_tick`, `work_item.sync_changed`, `stats.updated`. **NEW** at minimum as a unified multiplexed feed.

---

## 2. Chat / threads

Existing chat components (`ThreadView`, `Composer`) already consume a streaming thread API. Confirm these exist:

| Method | Path | Purpose | Status |
|---|---|---|---|
| `GET` | `/api/threads/{chat_id}` | Load thread history. | assumed present |
| `WS`  | `/api/threads/{chat_id}/stream` | Live stream of StreamEvents. | assumed present |
| `POST`| `/api/threads/{chat_id}/messages` | Send user turn. | assumed present |
| `POST`| `/api/threads/{chat_id}/cancel` | Cancel in-flight turn. | assumed present |

New needs from the redesign:

| Method | Path | Purpose | Status |
|---|---|---|---|
| `GET` | `/api/threads/{chat_id}/events/{event_id}` | Raw StreamEvent JSON for the inspector. | **NEW** if events aren't addressable individually |
| `GET` | `/api/threads/{chat_id}/tool-calls/{call_id}` | Full tool-call payload (inputs + outputs) for inspector. | **NEW** |
| `GET` | `/api/threads/{chat_id}/token-usage` | Rolling token counts and cost estimate. | **NEW** |
| `POST`| `/api/threads/{chat_id}/replay` | Replay events at a client-chosen speed (client-side ideally, but may need a server cursor). | optional |

---

## 3. Work items

Work items are first-class, git-synced, and managed by the **context backend** (see `context-backend-design/requirements.md`). The frontend needs a thin HTTP facade over that backend.

| Method | Path | Purpose | Status |
|---|---|---|---|
| `GET` | `/api/work` | List work items with sync state: `[{ work_id, name, work_dir, sync: { state, ahead, behind, dirty, last_synced_at }, session_counts: {...}, last_activity_at }]`. | **NEW** |
| `GET` | `/api/work/{work_id}` | Full work item detail: paths, config, roots, recent artifacts. | **NEW** |
| `POST`| `/api/work` | Create new work item (name, optional template). | **NEW** |
| `POST`| `/api/work/{work_id}/sync` | Trigger git pull/push reconcile. Returns a sync operation id. | **NEW** |
| `GET` | `/api/work/{work_id}/sync/{op_id}` | Poll sync op. | **NEW** |
| `POST`| `/api/work/{work_id}/archive` | Soft-hide. | **NEW** |
| `GET` | `/api/work/active` | Read the globally-active work item for the current user session. | **NEW** |
| `PUT` | `/api/work/active` | Set active work item. | **NEW** |

Live updates (via `/api/stream`): `work_item.sync_changed`, `work_item.activity`.

---

## 4. Files

Backed by the context backend's index + raw fs reads within allowed roots.

| Method | Path | Purpose | Status |
|---|---|---|---|
| `GET` | `/api/files/tree?scope=work|spawn|repo&id=<work_id/spawn_id>&path=` | Directory tree (lazy, children-only). Returns `[{ name, kind, size, mtime, git_status }]`. | **NEW** |
| `GET` | `/api/files/read?scope=&id=&path=&range=` | File content, range-supported for large files. | **NEW** |
| `GET` | `/api/files/diff?scope=&id=&path=&ref_a=&ref_b=` | Unified diff between two refs (or HEAD). | **NEW** |
| `GET` | `/api/files/meta?scope=&id=&path=` | Metadata: size, mtime, git log (short), referenced-by (sessions). | **NEW** |
| `GET` | `/api/files/search?q=&scope=&id=` | Fuzzy filename search, used by `⌘K` and `@file` mention. | **NEW** |

Security constraints: every path is validated against the scope's allowed roots server-side; symlinks that escape are refused.

---

## 5. Context / config

| Method | Path | Purpose | Status |
|---|---|---|---|
| `GET` | `/api/context` | `meridian context --json` equivalent. | assumed present or **NEW** |
| `GET` | `/api/config` | Resolved config (read-only). | **NEW** if not present |
| `GET` | `/api/models` | Model catalog + routing hints. | **NEW** |
| `GET` | `/api/agents` | Available agents (from `.agents/`). | **NEW** |

---

## 6. Health / system

| Method | Path | Purpose | Status |
|---|---|---|---|
| `GET` | `/api/health` | Backend health, git daemon status, context backend status. | assumed present |
| `GET` | `/api/version` | Build version for "About". | assumed present |

---

## 7. Cross-cutting

- **CORS:** needed only if the Vite dev server runs on a different port; production serves from 7676.
- **Auth:** v1 assumes localhost-only; add a shared-secret header (`X-Meridian-Token`) in config for exposed deployments.
- **Streaming protocol:** prefer a single SSE endpoint `/api/stream` with subscription query params over many WS connections, except the existing per-thread WS which stays.
- **Cursors & pagination:** all list endpoints use opaque cursors, not offsets.
- **Idempotency:** `POST /api/spawns` and `/api/work/*/sync` accept `Idempotency-Key` header.

---

## 8. Minimum new-endpoint set to ship v1

Short list the @frontend-coder and backend owner should treat as the v1 cut:

1. `GET /api/spawns` with filters + cursors.
2. `GET /api/spawns/stats`.
3. `GET /api/stream` (SSE, multiplexed).
4. `POST /api/spawns/{id}/fork`, `/cancel`, `/archive`.
5. `GET /api/work`, `GET/POST /api/work/{id}`, `POST /api/work/{id}/sync`, `GET/PUT /api/work/active`.
6. `GET /api/files/tree`, `/read`, `/diff`, `/meta`, `/search`.
7. `GET /api/threads/{id}/tool-calls/{call_id}` + token-usage.
8. `GET /api/agents`, `GET /api/models`.

Everything else is either already present or can wait for fast-follow.
