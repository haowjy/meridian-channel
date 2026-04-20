# Sidebar Design

## Overview

The sidebar organizes sessions by work items. It's the primary navigation for quickly switching between work contexts.

```
┌─────────────────────────────────┐
│ WORK                    [+ ▾]  │
├─────────────────────────────────┤
│ ▼ ● auth-middleware             │
│     ● p42 orchestrator   2m    │
│     ● p43 coder          5m    │
│     ✓ p44 reviewer      10m    │
│                                 │
│ ▼ ○ spawn-tree-view             │
│     ✓ p51 coder         30m    │
│                                 │
│ ▶ ✓ api-docs-update             │
│                                 │
├─────────────────────────────────┤
│ QUICK                           │
├─────────────────────────────────┤
│   ○ p60 Fix that one...   2m   │
│   ✓ p55 What's the syn... 1h   │
│                                 │
└─────────────────────────────────┘
```

## Structure

The sidebar has two sections:

1. **Work** — Sessions grouped under work items
2. **Quick** — Unattached sessions

Each section is collapsible.

## Work Section

### Work Item Groups

Each work item is a collapsible group:

```
▼ ● auth-middleware                  ← Work item header (collapsible)
    ● p42 orchestrator   2m          ← Session row
    ● p43 coder          5m
    ✓ p44 reviewer      10m
```

### Work Item Header

```
┌─────────────────────────────────────────────────────┐
│ [▼/▶] [status] [work_id]                            │
└─────────────────────────────────────────────────────┘
```

- Chevron: expand/collapse the group
- Status: aggregate status from child sessions
- Work ID: the work item slug

### Session Row

```
┌─────────────────────────────────────────────────────┐
│     [status] [spawn_id] [agent]            [time]   │
└─────────────────────────────────────────────────────┘
```

- Indented to show hierarchy
- Status dot
- Spawn ID (monospace)
- Agent name (or harness if no agent)
- Relative timestamp

### Ordering

Work items ordered by most recent activity (newest first).
Sessions within a work item ordered by creation time (oldest first, so the workflow reads top-to-bottom).

## Quick Section

Flat list of unattached sessions:

```
○ p60 Fix that one...   2m
✓ p55 What's the syn... 1h
```

Ordered by creation time (newest first).

## Interactions

### Work Item Header

| Action | Behavior |
|--------|----------|
| Click chevron | Toggle expand/collapse |
| Click name | Navigate to work item detail |
| Right-click | Context menu |

### Session Row

| Action | Behavior |
|--------|----------|
| Click | Navigate to session view |
| Double-click | Navigate + focus composer |
| Right-click | Context menu |

### Context Menus

**Work Item:**
- View work item
- Create new session in work
- Archive work item
- Copy work ID

**Session:**
- View session
- Cancel (if running)
- Attach to work (if unattached)
- Detach from work
- Copy spawn ID
- Copy session ID

## Header Actions

```
┌─────────────────────────────────┐
│ WORK                    [+ ▾]  │
└─────────────────────────────────┘
```

The `[+ ▾]` dropdown:
- **New session** — opens composer
- **New work item** — opens work creation dialog
- **View all work** — navigates to work list view

## Visual States

### Selected Session

The currently viewed session is highlighted:

```
▼ ● auth-middleware
    ● p42 orchestrator   2m    ← highlighted
    ● p43 coder          5m
```

Background color: `bg-accent/10` with left border accent.

### Collapsed Work Item

Shows aggregate info when collapsed:

```
▶ ● auth-middleware (3)
```

The `(3)` shows session count.

### Empty Work Item

Work items with no sessions yet:

```
▼ ○ new-feature
    No sessions yet
    [Start session]
```

## Component Structure

```
Sidebar/
├── Sidebar.tsx               ← Main container
├── SidebarHeader.tsx         ← Logo + new button
├── WorkSection.tsx           ← Work items section
│   ├── WorkItemGroup.tsx     ← Collapsible work item
│   └── SessionRow.tsx        ← Session list item
├── QuickSection.tsx          ← Unattached sessions
└── hooks/
    ├── useSidebarData.ts     ← Data fetching
    └── useSidebarState.ts    ← Expansion state
```

### Sidebar.tsx

```tsx
interface SidebarProps {
  selectedSessionId?: string
  onSessionSelect: (sessionId: string) => void
  onWorkSelect: (workId: string) => void
}

function Sidebar({ selectedSessionId, onSessionSelect, onWorkSelect }: SidebarProps) {
  const { workItems, quickSessions, isLoading } = useSidebarData()
  const { expandedWorkIds, toggleWork } = useSidebarState()

  return (
    <aside className="w-64 border-r border-border flex flex-col h-full">
      <SidebarHeader />
      
      <div className="flex-1 overflow-y-auto">
        <WorkSection
          workItems={workItems}
          expandedIds={expandedWorkIds}
          selectedSessionId={selectedSessionId}
          onToggle={toggleWork}
          onSessionSelect={onSessionSelect}
          onWorkSelect={onWorkSelect}
        />
        
        <QuickSection
          sessions={quickSessions}
          selectedSessionId={selectedSessionId}
          onSessionSelect={onSessionSelect}
        />
      </div>
    </aside>
  )
}
```

### WorkItemGroup.tsx

```tsx
interface WorkItemGroupProps {
  workItem: WorkItemWithSessions
  expanded: boolean
  selectedSessionId?: string
  onToggle: () => void
  onSessionSelect: (sessionId: string) => void
  onWorkSelect: () => void
}

function WorkItemGroup({
  workItem,
  expanded,
  selectedSessionId,
  onToggle,
  onSessionSelect,
  onWorkSelect,
}: WorkItemGroupProps) {
  const status = deriveWorkStatus(workItem.sessions)
  
  return (
    <div>
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2 px-2 py-1.5 hover:bg-bg-2"
      >
        <ChevronRight className={cn("w-4 h-4 transition-transform", expanded && "rotate-90")} />
        <StatusDot status={status} size="sm" />
        <span className="font-mono text-sm truncate flex-1 text-left">
          {workItem.work_id}
        </span>
        {!expanded && (
          <span className="text-xs text-muted">({workItem.sessions.length})</span>
        )}
      </button>
      
      {expanded && (
        <div className="pl-4">
          {workItem.sessions.map(session => (
            <SessionRow
              key={session.session_id}
              session={session}
              selected={session.session_id === selectedSessionId}
              onSelect={() => onSessionSelect(session.session_id)}
            />
          ))}
          {workItem.sessions.length === 0 && (
            <div className="px-2 py-2 text-xs text-muted">
              No sessions yet
            </div>
          )}
        </div>
      )}
    </div>
  )
}
```

### SessionRow.tsx

```tsx
interface SessionRowProps {
  session: SessionSummary
  selected: boolean
  onSelect: () => void
}

function SessionRow({ session, selected, onSelect }: SessionRowProps) {
  return (
    <button
      onClick={onSelect}
      className={cn(
        "w-full flex items-center gap-2 px-2 py-1 hover:bg-bg-2 text-left",
        selected && "bg-accent/10 border-l-2 border-l-accent"
      )}
    >
      <StatusDot status={session.status} size="sm" />
      <span className="font-mono text-xs">{session.spawn_id}</span>
      <span className="text-xs text-muted truncate flex-1">
        {session.agent || session.harness}
      </span>
      <RelativeTime date={session.created_at} className="text-xs text-muted" />
    </button>
  )
}
```

## Data Fetching

### API Call

`GET /api/sidebar`

```json
{
  "work_items": [
    {
      "work_id": "auth-middleware",
      "status": "active",
      "last_activity": "2026-04-19T14:30:00Z",
      "sessions": [
        {
          "session_id": "a7f3b2c1",
          "spawn_id": "p42",
          "status": "running",
          "agent": "dev-orchestrator",
          "harness": "claude",
          "created_at": "..."
        }
      ]
    }
  ],
  "quick_sessions": [
    {
      "session_id": "b8c4d3e2",
      "spawn_id": "p60",
      "status": "idle",
      "prompt": "Fix that one...",
      "harness": "claude",
      "created_at": "..."
    }
  ]
}
```

### Polling

Poll every 5 seconds to update status badges. Use SWR or React Query with:
- `revalidateOnFocus: true`
- `refreshInterval: 5000`

### WebSocket Updates (Future)

Subscribe to status change events to avoid polling:

```json
{"type": "session_status_changed", "session_id": "a7f3b2c1", "status": "succeeded"}
{"type": "work_item_created", "work_id": "new-feature"}
```

## Persistence

### Expansion State

Store expanded work IDs in localStorage:

```typescript
const STORAGE_KEY = 'sidebar:expanded'

function useSidebarState() {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored ? new Set(JSON.parse(stored)) : new Set()
  })
  
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...expandedIds]))
  }, [expandedIds])
  
  // ...
}
```

### Auto-Expand Active

When navigating to a session, auto-expand its parent work item if collapsed.

## Responsive Behavior

| Width | Behavior |
|-------|----------|
| < 1024px | Sidebar collapses to icons only |
| 1024+ | Full sidebar |

In collapsed mode:
- Work items show as colored dots
- Hovering shows tooltip with work ID
- Clicking expands the sidebar temporarily
