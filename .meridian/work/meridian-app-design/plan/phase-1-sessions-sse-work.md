# Phase 1: Sessions, SSE, and Work Facade

## Scope and Boundaries

Deliver the backend surface that unblocks Sessions mode:

- `GET /api/spawns` with opaque cursor pagination and dashboard filters
- `GET /api/spawns/stats`
- `GET /api/spawns/{spawn_id}/events`
- `GET /api/stream` multiplexed SSE feed
- `GET /api/work`
- `GET /api/work/{work_id}`
- `POST /api/work`
- `POST /api/work/{work_id}/archive`
- `GET /api/work/active`
- `PUT /api/work/active`
- app-side sync contract for:
  - `POST /api/work/{work_id}/sync`
  - `GET /api/work/{work_id}/sync/{op_id}`

In scope:

- minimal route/service extraction under `src/meridian/lib/app/`
- additive `SpawnManager` broadcast changes needed for SSE and multi-watch support
- reuse of existing spawn/work ops wherever the repo already has authoritative logic
- opaque cursor discipline for list endpoints

Out of scope:

- file tree/read/diff/search/meta endpoints
- spawn `fork` and `archive`
- catalog and inspector endpoints
- changing per-thread websocket behavior beyond what is required for shared subscription safety

## Touched Files and Modules

- Existing:
  - `src/meridian/lib/app/server.py`
  - `src/meridian/lib/app/ws_endpoint.py`
  - `src/meridian/lib/streaming/spawn_manager.py`
  - `src/meridian/lib/ops/spawn/api.py`
  - `src/meridian/lib/ops/work_dashboard.py`
  - `src/meridian/lib/ops/work_lifecycle.py`
  - `src/meridian/lib/ops/context.py`
  - `tests/integration/launch/test_app_server.py`
  - `tests/integration/launch/test_app_agui_phase3.py`
- Planned new app modules:
  - `src/meridian/lib/app/api_models.py`
  - `src/meridian/lib/app/stream.py`
  - `src/meridian/lib/app/spawn_routes.py`
  - `src/meridian/lib/app/work_routes.py`
  - `tests/integration/launch/test_app_stream.py`
  - `tests/integration/launch/test_app_work_api.py`

## Claimed Contract IDs

- `APP-SESS-01`
- `APP-SESS-02`
- `APP-SESS-03`
- `APP-SESS-04`
- `APP-WORK-01`
- `APP-WORK-02`
- `APP-WORK-03`

## Touched Refactor IDs

- none from local design package

## Dependencies

- `backend-gaps.md`
- `design/server-lifecycle.md`
- `design/session-registry.md`
- existing spawn/work ops modules listed above
- external precondition for full `APP-WORK-03` closure: a concrete context-backend/hook-backed sync runner or an explicitly approved temporary adapter implementation

## Subphases

### 1.1 App Route and Projection Extraction

**Scope**

- Split the current monolithic `server.py` into reusable route/service seams before adding more endpoint logic.
- Introduce shared response/request models for:
  - cursor envelopes
  - spawn dashboard projections
  - work list/detail projections
  - SSE event envelopes

**Files / modules touched**

- `src/meridian/lib/app/server.py`
- `src/meridian/lib/app/api_models.py`
- `src/meridian/lib/app/spawn_routes.py`
- `src/meridian/lib/app/work_routes.py`

**Dependencies**

- none

**Light verification**

- existing app route-registration tests still pass
- no existing spawn create/cancel/ws behavior regresses

**Estimated size**

- medium

### 1.2 Spawn Query, Stats, and Live Feed

**Scope**

- Expand `GET /api/spawns` from an ID list into a dashboard-ready cursor endpoint with filters for `work_id`, `status`, `agent`, and sensible default ordering.
- Reuse `spawn_stats_sync()` for `GET /api/spawns/stats`.
- Add:
  - `GET /api/spawns/{spawn_id}/events` for per-spawn tail/cursor reads
  - `GET /api/stream` SSE for multiplexed live updates
- Change `SpawnManager` fan-out from single-subscriber to multi-subscriber broadcast so websocket and SSE consumers can coexist.

**Files / modules touched**

- `src/meridian/lib/app/server.py`
- `src/meridian/lib/app/spawn_routes.py`
- `src/meridian/lib/app/stream.py`
- `src/meridian/lib/app/ws_endpoint.py`
- `src/meridian/lib/streaming/spawn_manager.py`
- `src/meridian/lib/ops/spawn/api.py`
- `tests/integration/launch/test_app_server.py`
- `tests/integration/launch/test_app_stream.py`

**Dependencies**

- Subphase 1.1

**Light verification**

- integration tests cover:
  - opaque cursor behavior
  - stats projection shape
  - SSE event framing and reconnect-safe cursors
  - simultaneous websocket + SSE subscribers on one spawn
- existing websocket tests still pass

**Estimated size**

- large

### 1.3 Work CRUD and Active-Work Facade

**Scope**

- Add app routes that reuse current work-item ops for:
  - list/detail/create/archive
  - active-work read/write
- Enrich list/detail responses with the fields the app design expects:
  - work directory
  - session/spawn counts
  - last activity
  - sync projection slot

**Files / modules touched**

- `src/meridian/lib/app/work_routes.py`
- `src/meridian/lib/app/api_models.py`
- `src/meridian/lib/ops/work_dashboard.py`
- `src/meridian/lib/ops/work_lifecycle.py`
- `src/meridian/lib/ops/context.py`
- `tests/integration/launch/test_app_work_api.py`

**Dependencies**

- Subphase 1.1

**Light verification**

- integration tests cover create/list/detail/archive/active read-write flows
- active-work mutation uses existing session attachment behavior rather than a duplicate store

**Estimated size**

- medium

### 1.4 Work Sync Adapter and Operation Tracking

**Scope**

- Define the app-side contract for work sync:
  - request validation
  - durable operation IDs
  - pollable status projection
  - SSE status updates (`work_item.sync_changed`)
- Implement the adapter seam that delegates actual sync execution to context-backend/hook infrastructure.
- Do not embed bespoke git orchestration inside the FastAPI handler unless the project explicitly approves that as the temporary backend.

**Files / modules touched**

- `src/meridian/lib/app/work_routes.py`
- `src/meridian/lib/app/stream.py`
- planned new module: `src/meridian/lib/app/work_sync.py`
- `tests/integration/launch/test_app_work_api.py`

**Dependencies**

- Subphase 1.3
- concrete sync backend decision

**Light verification**

- fake-backend integration tests cover trigger + poll contract
- if real backend exists, smoke test proves one successful sync operation end to end on a disposable git-backed work context

**Estimated size**

- medium, but externally constrained

## Phase Exit Gate

- `@verifier`
  - app/server integration suite passes for touched files
  - `ruff` and `pyright` stay green
- `@integration-tester`
  - cursor/filter contract for `/api/spawns`
  - multi-subscriber SSE behavior
  - work CRUD and active-work flows
  - sync trigger/poll contract at least against the adapter seam
- `@smoke-tester`
  - live local server run verifies:
    - `/api/stream` emits spawn updates
    - status bar counters from `/api/spawns/stats` match observed state
    - active work switches are visible across requests
    - real sync run only if concrete backend exists

## Exit Criteria

- Sessions mode can read filtered spawn lists, stats, and a unified live feed without polling every spawn individually.
- Work list/detail/create/archive/active endpoints are app-ready and backed by existing work state logic.
- `APP-WORK-03` is either fully wired to a real sync backend or remains explicitly blocked in `plan/status.md`; it must not be silently downgraded.
