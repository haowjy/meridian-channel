# Dashboard Layout

## Work-Item-Centric Organization

The dashboard is organized around **work items as first-class entities**. Sessions are grouped under their work items, with unattached sessions in a separate section.

This replaces the earlier repo-grouped design. Work items are the user's mental model for "what am I doing" — repos are infrastructure.

## Layout Structure

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ┌────────┬───────────────────────────────────────────────────────────────────┤
│ │        │                                                                   │
│ │ Activ- │  ┌─────────────────────────────────────────────────────────────┐  │
│ │ ity    │  │ ACTIVE WORK                                                 │  │
│ │ Bar    │  ├─────────────────────────────────────────────────────────────┤  │
│ │        │  │ ┌─────────────────────────────────────────────────────────┐ │  │
│ │ [🏠]   │  │ │ ● auth-middleware                              1h ago   │ │  │
│ │ [📁]   │  │ │   Implement JWT validation for API routes               │ │  │
│ │ [⚡]   │  │ │                                                          │ │  │
│ │        │  │ │   ● p42 orchestrator  ● p43 coder  ✓ p44 reviewer       │ │  │
│ │        │  │ └─────────────────────────────────────────────────────────┘ │  │
│ │        │  │ ┌─────────────────────────────────────────────────────────┐ │  │
│ │        │  │ │ ● spawn-tree-view                              30m ago  │ │  │
│ │        │  │ │   Build spawn tree visualization component              │ │  │
│ │        │  │ │                                                          │ │  │
│ │        │  │ │   ● p51 coder                                           │ │  │
│ │        │  │ └─────────────────────────────────────────────────────────┘ │  │
│ │        │  └─────────────────────────────────────────────────────────────┘  │
│ │        │                                                                   │
│ │        │  ┌─────────────────────────────────────────────────────────────┐  │
│ │        │  │ QUICK SESSIONS                                              │  │
│ │        │  ├─────────────────────────────────────────────────────────────┤  │
│ │        │  │ ┌─────────────────────┐ ┌─────────────────────┐             │  │
│ │        │  │ │ ○ p60               │ │ ✓ p55               │             │  │
│ │        │  │ │ Fix that one bug... │ │ What's the syntax...│             │  │
│ │        │  │ │ claude · opus       │ │ claude · sonnet     │             │  │
│ │        │  │ └─────────────────────┘ └─────────────────────┘             │  │
│ │        │  └─────────────────────────────────────────────────────────────┘  │
│ │        │                                                                   │
│ │ ────── │  ┌─────────────────────────────────────────────────────────────┐  │
│ │ [⚙]   │  │                                                              │  │
│ │        │  │     What would you like to work on?                         │  │
│ │        │  │     ┌─────────────────────────────────────────────────────┐ │  │
│ │        │  │     │                                                     │ │  │
│ │        │  │     │                                                     │ │  │
│ │        │  │     └─────────────────────────────────────────────────────┘ │  │
│ │        │  │     [Quick ○ ● Thorough]            [Advanced ▾]   [Send]  │  │
│ │        │  └─────────────────────────────────────────────────────────────┘  │
│ └────────┴───────────────────────────────────────────────────────────────────┤
│                                                                 Status Bar   │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Activity Bar

Vertical icon bar on the left edge (48px wide), providing top-level navigation:

| Icon | Label | Target |
|------|-------|--------|
| 🏠 Home | Dashboard view |
| 📁 Explorer | File explorer panel |
| ⚡ Sessions | All sessions list |
| ─── | Separator |
| ⚙ Settings | Settings panel |

The activity bar is always visible. Clicking an icon either:
1. Navigates to a view (Home, Sessions)
2. Toggles a side panel (Explorer, Settings)

## Sections

### Active Work

Work items with at least one non-terminal session. Ordered by most recent activity.

Each work item card shows:
- Status indicator (● running if any child is running)
- Work item ID (slug)
- Description (from work item metadata or first session prompt)
- Time since last activity
- Session chips showing child sessions with status

### Quick Sessions

Sessions not attached to any work item. These are exploratory, one-off, or not-yet-organized work.

Displayed as smaller cards in a grid or list. Each shows:
- Status indicator
- Spawn ID
- Prompt preview (first ~50 chars)
- Harness + model badges

### Composer (New Session)

Always visible at the bottom of the dashboard. The primary entry point for new work.

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  What would you like to work on?                                │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [Textarea: initial prompt]                                     │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  [Quick ○ ● Thorough]                   [Advanced ▾]    [Send]  │
└─────────────────────────────────────────────────────────────────┘
```

**Effort Toggle**: Quick (fast, cheaper) vs Thorough (deeper thinking). Default: Thorough.

**Advanced Panel** (collapsed by default):
- Harness selector (claude/codex/opencode)
- Model dropdown
- Agent profile dropdown
- Work item selector (attach to existing or create new)

## Interactions

### Work Item Card

| Action | Behavior |
|--------|----------|
| Click card body | Navigate to work item detail view |
| Click session chip | Navigate to that session |
| Hover card | Subtle highlight, show quick actions |
| Right-click | Context menu: archive, rename, delete |

### Session Card (Quick Sessions)

| Action | Behavior |
|--------|----------|
| Click | Navigate to session view |
| Hover | Show "attach to work" action |
| Right-click | Context menu: attach, cancel, delete |

### Composer

| Action | Behavior |
|--------|----------|
| Enter (empty field) | No-op |
| Enter (with text) | Submit, create session |
| Shift+Enter | Newline |
| Tab in Advanced | Cycle through controls |

## Data Requirements

### Work Items Endpoint

`GET /api/work-items` (new endpoint)

```json
{
  "items": [
    {
      "work_id": "auth-middleware",
      "description": "Implement JWT validation for API routes",
      "status": "active",
      "repo_root": "/home/user/meridian-cli",
      "repo_name": "meridian-cli",
      "sessions": [
        {
          "session_id": "a7f3b2c1",
          "spawn_id": "p42",
          "status": "running",
          "agent": "dev-orchestrator",
          "created_at": "..."
        }
      ],
      "last_activity": "2026-04-19T14:30:00Z"
    }
  ]
}
```

### Unattached Sessions

`GET /api/sessions?unattached=true`

Returns sessions where `work_id` is null.

## Empty States

### No Work Items

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  No active work yet                                             │
│                                                                 │
│  Start a new session below, or create a work item               │
│  from the CLI with `meridian work start`                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### No Quick Sessions

Section simply doesn't appear.

## Responsive Behavior

| Width | Behavior |
|-------|----------|
| < 1280px | Work cards stack vertically, session chips wrap |
| 1280-1600px | Standard layout |
| > 1600px | Work cards can show more session chips |
