# Frontend Routing

## Status

This document is superseded by:

- `../ui-spec.md` (canonical UI navigation model)
- `../backend-gaps.md` (canonical API surface)

Legacy route definitions in this file (`/`, `/s/:sessionId`, `/w/:workId`) are no longer canonical.

## Canonical Route Model (v1)

Mode is first-class route state. The app has exactly three primary routes:

| Route | Mode | Purpose |
|---|---|---|
| `/sessions` | Sessions | Dashboard of spawns grouped by work item, filters, and launch flow |
| `/chat` | Chat | Conversation surface with SessionList + thread panes |
| `/files` | Files | Artifact/context browser with tree + preview/diff |

Notes:

- Unknown paths redirect to `/sessions`.
- Session/work/file selection is mode state (query/hash/app state), not path segments like `/s/:id`.

## API Alignment

Frontend routing and mode views must bind to spawn-first backend paths:

- `/api/spawns*` for Sessions and spawn operations
- `/api/threads*` for Chat streaming/history
- `/api/files*` for Files mode browsing and previews

Do not introduce new `/api/sessions*` or `/api/explorer*` dependencies in routing-layer decisions.

## Migration Mapping From Legacy Routes

| Legacy route | Replacement |
|---|---|
| `/` | `/sessions` |
| `/s/:sessionId` | `/chat` with selected spawn/session in state |
| `/w/:workId` | `/sessions` with `work_id` filter/state |
