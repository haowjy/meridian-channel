# Dashboard Layout

## Scope

This document specifies the **Sessions mode** viewport (`/sessions`) from `../ui-spec.md`.

- Canonical global shell (ModeRail/TopBar/StatusBar) lives in `../ui-spec.md`.
- Canonical endpoint contract lives in `../backend-gaps.md`.

## Sessions Mode Structure

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Sessions                                           [+ New session]  [I] │
├─────────────────────────────────────────────────────────────────────────┤
│ Filters: all | running | queued | done | failed   work: ▾   agent: ▾   │
├─────────────────────────────────────────────────────────────────────────┤
│ ▾ auth-refactor                         6 sessions · git:ahead 1 · ↻   │
│   ● p281  plan               claude-opus-4.7   running   2m    42%     │
│   ● p280  frontend-coder     claude-sonnet     running   4m     —      │
│   ✓ p274  designer           claude-opus-4.7   done     12m             │
│                                                                         │
│ ▸ (unattached)                          2 sessions                      │
└─────────────────────────────────────────────────────────────────────────┘
```

## Layout Rules

- Group rows by `work_id`, with a dedicated `(unattached)` group for null `work_id`.
- Default order: groups by latest activity desc; rows within group by created_at desc.
- `SessionRow` click switches to `/chat` and selects that spawn.
- `+ New session` opens modal; creation does not require route change before submit.
- StatusBar counters filter this mode when clicked.

## Key Components

### WorkItemGroup

- Header fields: `work_id`, session count, git sync badge, last activity.
- Header actions: expand/collapse, optional sync trigger.

### SessionRow

Fixed columns:

```
[status-dot] [spawn_id] [agent] [model] [state-text] [elapsed] [progress]
```

Row actions:

- Primary click: open in `/chat`.
- Overflow menu: cancel, fork, archive, open logs.

### Filter Bar

- Status chip set (`all/running/queued/done/failed`).
- Work and agent selectors.
- Filter state is URL/state-persisted for reload and deep-linking.

### New Session Dialog

Required fields:

- `agent`
- `prompt`

Optional fields:

- `model`
- `work_id`
- `reference_files[]`

Footer shows resolved spawn payload preview.

## Data Requirements (canonical)

### Sessions list

`GET /api/spawns?work_id=&status=&agent=&limit=&cursor=`

### Sessions counters

`GET /api/spawns/stats?work_id=`

### Work metadata

`GET /api/work`

Used for work names, sync badges, and ordering hints.

### Live updates

`GET /api/stream` (SSE) or `WS /api/stream`

Expected events used by this mode:

- `spawn.created`
- `spawn.state_changed`
- `spawn.finalized`
- `spawn.activity_tick`
- `work_item.sync_changed`
- `stats.updated`

## Empty States

- No sessions: show CTA to create first session.
- No rows after filter: show "No sessions match current filters" and clear-filter action.

## Non-canonical content removed

The following legacy assumptions were removed from this doc:

- `/api/work-items`
- `/api/sessions?unattached=true`
- Activity bar routes (`Home/Explorer/Sessions`) as top-level navigation model
