# Pre-Planning Notes

## Inputs Used

- `backend-gaps.md` is the canonical backend contract for this plan.
- Supporting design context came from:
  - `design/server-lifecycle.md`
  - `design/overview.md`
  - `design/session-registry.md`
  - `design/file-explorer.md`
  - `features.md`
- Current implementation surfaces inspected:
  - `src/meridian/lib/app/server.py`
  - `src/meridian/lib/app/ws_endpoint.py`
  - `src/meridian/lib/streaming/spawn_manager.py`
  - `src/meridian/lib/ops/spawn/api.py`
  - `src/meridian/lib/ops/work_dashboard.py`
  - `src/meridian/lib/ops/work_lifecycle.py`
  - `src/meridian/lib/ops/context.py`
  - `src/meridian/lib/ops/catalog.py`
  - `src/meridian/lib/harness/common.py`

## Observed Current State

- App server currently exposes only:
  - `POST /api/spawns`
  - `GET /api/spawns`
  - `GET /api/spawns/{spawn_id}`
  - `POST /api/spawns/{spawn_id}/inject`
  - `POST /api/spawns/{spawn_id}/cancel`
  - `WS /api/spawns/{spawn_id}/ws`
- `spawn_stats_sync()` already exists in `src/meridian/lib/ops/spawn/api.py` and should be reused rather than reimplemented.
- Work list/detail/active-attachment primitives already exist in:
  - `src/meridian/lib/ops/work_dashboard.py`
  - `src/meridian/lib/ops/work_lifecycle.py`
  - `src/meridian/lib/ops/context.py`
- `SpawnManager.subscribe()` is single-subscriber today. That blocks a unified SSE feed and also prevents multiple watchers on one spawn.
- No app file API exists yet. No reusable path-security helper exists for project-root-relative validation.
- No work-sync execution surface exists in current app/server/work ops. Context-backend artifacts assign that behavior to future context/hook infrastructure.
- Existing app tests cover only create-spawn and websocket behavior. There is no current integration coverage for `/api/work`, `/api/files`, `/api/stream`, catalog, or inspector endpoints.

## Missing Planning Inputs

- No `design/spec/` tree exists in this work item.
- No local `design/refactors.md` or `design/feasibility.md` exists in this work item.
- No existing `plan/` package existed before this plan.

## Planning Adaptation

- This plan derives stable contract IDs from `backend-gaps.md` (`APP-*`) and uses those IDs in `plan/leaf-ownership.md`.
- Refactor handling is scoped to app-route/service extraction required to keep the implementation reviewable; there is no external refactor agenda file to mirror.
- Work-sync is planned as an explicit integration seam. Phase 1 can shape the app-side contract immediately, but full closure of the sync endpoints depends on a concrete backend runner.
