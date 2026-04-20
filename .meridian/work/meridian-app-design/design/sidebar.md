# Sidebar / SessionList Design

## Scope

This doc defines the **SessionList panel** used in:

- `/sessions` mode (full-width list context)
- `/chat` mode (left rail, ~240 px)

Canonical UX source remains `../ui-spec.md`.

## Structure

SessionList is work-grouped and includes an `(unattached)` group.

```
▼ auth-middleware
  ● p42 orchestrator   2m
  ● p43 coder          5m
  ✓ p44 reviewer      10m

▼ spawn-tree-view
  ✓ p51 coder         30m

▼ (unattached)
  ○ p60 Fix that one...  2m
```

## Ordering

- Groups ordered by latest activity desc.
- Rows inside a group ordered by created_at desc.
- Active row is accent-highlighted.

## Row Content

Each row renders:

- status dot
- `spawn_id` (monospace)
- agent/model summary (truncated)
- relative time

## Interactions

### Group header

- Toggle expand/collapse.
- Open group context menu (archive work, sync work, copy work id).

### Session row

- Click: switch to `/chat` and select this spawn.
- Optional double click: focus composer in current chat column.
- Context menu: cancel, fork, archive, copy spawn id, open logs.

## Data Contract (canonical)

SessionList does not call a dedicated `/api/sidebar` endpoint.

Required data comes from:

- `GET /api/spawns?work_id=&status=&agent=&limit=&cursor=`
- `GET /api/work`
- `GET /api/spawns/stats?work_id=` (optional badge counters)
- `GET /api/stream` / `WS /api/stream` for live updates

## Persistence

- Expansion state for work groups is persisted locally.
- Active selection comes from global mode state (route + selected spawn context).

## Notes

- Keep row primitive identical between Sessions mode and Chat mode.
- Chat mode uses the narrower variant (single-line truncation) but same semantics.

## Non-canonical content removed

Removed stale assumptions:

- dedicated `/api/sidebar` response shape
- separate "Quick" section as a structurally different data source
- navigation model tied to old app sidebar semantics
