# Plan Status

## Phase 1: Sessions, SSE, and Work Facade

**Status: COMPLETE** (2026-04-19)

### Subphases

| Subphase | Description | Status |
|----------|-------------|--------|
| 1.1 | Route/Service Extraction | ✅ Complete |
| 1.2 | Spawn Query/Stats/SSE | ✅ Complete |
| 1.3 | Work CRUD + Active Facade | ✅ Complete |
| 1.4 | Work Sync Adapter | ✅ Complete (501 stub) |

### New Files Created

- `src/meridian/lib/app/api_models.py` — Shared Pydantic models
- `src/meridian/lib/app/spawn_routes.py` — Spawn endpoints
- `src/meridian/lib/app/work_routes.py` — Work endpoints
- `src/meridian/lib/app/stream.py` — SSE streaming

### Files Modified

- `src/meridian/lib/app/server.py` — Refactored to use extracted modules

### Endpoints Implemented

**Spawn Endpoints:**
- `POST /api/spawns` — Create spawn (existing, extracted)
- `GET /api/spawns` — List spawns (existing, extracted)
- `GET /api/spawns/{spawn_id}` — Get spawn detail (existing, extracted)
- `POST /api/spawns/{spawn_id}/inject` — Inject message (existing, extracted)
- `POST /api/spawns/{spawn_id}/cancel` — Cancel spawn (existing, extracted)
- `GET /api/spawns/list` — **NEW** Paginated list with filters
- `GET /api/spawns/stats` — **NEW** Aggregated status counts
- `GET /api/spawns/{spawn_id}/events` — **NEW** Per-spawn event tail

**Work Endpoints:**
- `GET /api/work` — **NEW** List work items
- `GET /api/work/{work_id}` — **NEW** Get work item detail
- `POST /api/work` — **NEW** Create work item
- `POST /api/work/{work_id}/archive` — **NEW** Archive work item
- `GET /api/work/active` — **NEW** Get active work item
- `PUT /api/work/active` — **NEW** Set active work item
- `POST /api/work/{work_id}/sync` — **NEW** 501 stub
- `GET /api/work/{work_id}/sync/{op_id}` — **NEW** 501 stub

**Streaming Endpoints:**
- `GET /api/stream` — **NEW** SSE multiplexed feed (keepalive-based for now)

### Verification

- ✅ pyright: 0 errors
- ✅ ruff: all checks passed
- ✅ 82 existing tests pass
- ✅ No regressions on spawn create/cancel/ws behavior

### Blockers for APP-WORK-03 (Work Sync)

Work sync remains explicitly blocked pending hook infrastructure:
- `POST /api/work/{work_id}/sync` returns 501
- `GET /api/work/{work_id}/sync/{op_id}` returns 501

This is intentional per the plan to avoid embedding ad hoc git logic in route handlers.

## Phase 2: Files Mode and Spawn Lifecycle

**Status: COMPLETE** (2026-04-19)

### Subphases

| Subphase | Description | Status |
|----------|-------------|--------|
| 2.1 | Path Security Foundation | ✅ Complete |
| 2.2 | File Tree/Read/Search/Meta | ✅ Complete |
| 2.3 | File Diff + Spawn Archive | ✅ Complete |

### New Files Created

- `src/meridian/lib/app/path_security.py` — Path validation and symlink escape prevention
- `src/meridian/lib/app/file_service.py` — File operations layer
- `src/meridian/lib/app/file_routes.py` — FastAPI file endpoints
- `tests/unit/app/test_path_security.py` — 35 path security tests
- `tests/integration/app/test_files_api.py` — 20 files API tests

### Endpoints Implemented

**Files Endpoints:**
- `GET /api/files/tree` — Directory tree listing
- `GET /api/files/read` — File content read with range support
- `GET /api/files/search` — Ripgrep-powered search
- `GET /api/files/meta` — File metadata (size, mtime, type)
- `GET /api/files/diff` — Git diff against refs

**Spawn Lifecycle:**
- `POST /api/spawns/{spawn_id}/archive` — Archive spawn
- `POST /api/spawns/{spawn_id}/fork` — Fork spawn (501 stub)

### Verification

- ✅ pyright: 0 errors
- ✅ ruff: all checks passed
- ✅ 35 path security unit tests pass
- ✅ 20 files API integration tests pass
- ✅ Smoke test verified all endpoints

### Security Verified

- ✅ Absolute path rejection
- ✅ Parent directory escape rejection
- ✅ Windows drive prefix rejection
- ✅ Symlink escape prevention

## Phase 3: Inspector and Catalog Endpoints

**Status: COMPLETE** (2026-04-20)

### Subphases

| Subphase | Description | Status |
|----------|-------------|--------|
| 3.1 | Catalog Endpoints | ✅ Complete |
| 3.2 | Thread Inspector | ✅ Complete |

### New Files Created

- `src/meridian/lib/app/inspector.py` — Artifact extraction layer
- `src/meridian/lib/app/catalog_routes.py` — Models and agents endpoints
- `src/meridian/lib/app/thread_routes.py` — Thread inspector routes
- `tests/integration/app/test_catalog_api.py` — 7 catalog tests
- `tests/integration/app/test_thread_api.py` — 20 thread inspector tests

### Endpoints Implemented

**Catalog Endpoints:**
- `GET /api/models` — Model catalog from `models_list_sync()`
- `GET /api/agents` — Agent profiles from `.agents/`

**Thread Inspector Endpoints:**
- `GET /api/threads/{chat_id}/events/{event_id}` — Raw event lookup
- `GET /api/threads/{chat_id}/tool-calls` — List all tool calls
- `GET /api/threads/{chat_id}/tool-calls/{call_id}` — Tool call detail
- `GET /api/threads/{chat_id}/token-usage` — Token usage summary

### Key Decisions

- Event IDs use `{spawn_id}:{line_index}` format (stable across restarts)
- Inspector reads from `artifacts/` not live logs
- Chat ID parameter accepts both `pN` (spawn) and `cN` (chat) formats

### Verification

- ✅ pyright: 0 errors
- ✅ ruff: all checks passed
- ✅ 27 new integration tests pass
- ✅ 52 total app integration tests pass
- ✅ Smoke tested: catalog, events, tool-calls, token-usage all responding
