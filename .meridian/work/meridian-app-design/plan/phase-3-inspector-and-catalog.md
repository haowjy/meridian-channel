# Phase 3: Inspector and Catalog Endpoints

## Scope and Boundaries

Deliver the remaining read-only backend surfaces used by the chat inspector and launch UI:

- `GET /api/agents`
- `GET /api/models`
- `GET /api/threads/{chat_id}/events/{event_id}`
- `GET /api/threads/{chat_id}/tool-calls/{call_id}`
- `GET /api/threads/{chat_id}/token-usage`

In scope:

- stable artifact-derived IDs for inspector links
- reuse of existing catalog discovery code
- reuse of existing artifact extraction helpers for usage/tool-call data

Out of scope:

- replay endpoints
- in-browser transcript editing
- new persistence formats unless current artifacts cannot support stable addressing

## Touched Files and Modules

- Existing:
  - `src/meridian/lib/app/server.py`
  - `src/meridian/lib/catalog/agent.py`
  - `src/meridian/lib/ops/catalog.py`
  - `src/meridian/lib/harness/common.py`
  - `src/meridian/lib/harness/claude.py`
  - `src/meridian/lib/ops/session_log.py`
- Planned new app modules:
  - `src/meridian/lib/app/catalog_routes.py`
  - `src/meridian/lib/app/thread_routes.py`
  - `src/meridian/lib/app/inspector.py`
  - `tests/integration/launch/test_app_catalog_api.py`
  - `tests/integration/launch/test_app_thread_api.py`

## Claimed Contract IDs

- `APP-CAT-01`
- `APP-CAT-02`
- `APP-THREAD-01`
- `APP-THREAD-02`
- `APP-THREAD-03`

## Touched Refactor IDs

- none from local design package

## Dependencies

- Phase 1
- Phase 2
- `backend-gaps.md`
- existing catalog and artifact extraction helpers

## Subphases

### 3.1 Catalog Endpoints

**Scope**

- Add `GET /api/models` by projecting `models_list_sync()` into app JSON.
- Add `GET /api/agents` by scanning `.agents/agents/*.md` through the catalog layer and returning app-friendly summaries.
- Keep route logic thin; discovery stays in catalog modules.

**Files / modules touched**

- `src/meridian/lib/app/catalog_routes.py`
- `src/meridian/lib/app/api_models.py`
- `src/meridian/lib/catalog/agent.py`
- `src/meridian/lib/ops/catalog.py`
- `tests/integration/launch/test_app_catalog_api.py`

**Dependencies**

- Phase 1 app route/service seams

**Light verification**

- integration tests cover empty/missing agents directory handling, normal catalog responses, and stable JSON field names

**Estimated size**

- small

### 3.2 Thread Event Addressing and Inspector Extractors

**Scope**

- Introduce deterministic event IDs derived from persisted transcript/artifact order so inspector requests survive restarts.
- Implement raw event lookup and tool-call lookup by reading persisted artifacts rather than live in-memory state.
- Reuse existing harness extraction helpers wherever they already parse usage/tool-call data.

**Files / modules touched**

- `src/meridian/lib/app/thread_routes.py`
- `src/meridian/lib/app/inspector.py`
- `src/meridian/lib/harness/common.py`
- `src/meridian/lib/harness/claude.py`
- `src/meridian/lib/ops/session_log.py`
- `tests/integration/launch/test_app_thread_api.py`

**Dependencies**

- Subphase 3.1 not required
- Phase 2 file/artifact read foundation

**Light verification**

- integration tests cover:
  - valid and invalid event IDs
  - tool-call lookup
  - token usage extraction from persisted artifacts
- no endpoint depends on live websocket or active connection presence

**Estimated size**

- medium

## Phase Exit Gate

- `@verifier`
  - touched integration tests pass
  - `ruff` and `pyright` stay green
- `@integration-tester`
  - catalog responses match current discovery behavior
  - inspector endpoints can read completed-session artifacts
  - token usage projection stays stable across harnesses with/without usage metadata
- `@smoke-tester`
  - live app can open inspector views on at least one completed spawn and one active or recently completed thread without relying on in-memory-only data

## Exit Criteria

- Launch UI can query available agents and models from app routes.
- Inspector links are stable across restarts because they address persisted artifacts, not ephemeral runtime counters.
- Token usage and tool-call detail endpoints work for completed sessions without requiring a live connection.
