# Session Cards

## Card Types

Two card variations based on context:

1. **Inline Session Chip** — compact, used within work item cards
2. **Session Card** — standalone, used in quick sessions grid and session list

## Inline Session Chip

Compact representation for showing multiple sessions within a work item card.

```
┌──────────────────┐
│ ● p42            │
│ orchestrator     │
└──────────────────┘
```

### Anatomy

```
┌─────────────────────────────────────┐
│ [status] [spawn_id]                 │  ← Row 1: status + ID
│ [agent | harness]                   │  ← Row 2: role identifier
└─────────────────────────────────────┘
```

### States

| Status | Visual |
|--------|--------|
| Running | `●` green pulsing dot |
| Idle | `○` gray hollow dot |
| Succeeded | `✓` green checkmark |
| Failed | `✗` red X |
| Cancelled | `⊘` amber slash |

### Interactions

| Action | Behavior |
|--------|----------|
| Click | Navigate to session view |
| Hover | Tooltip with full details |

### Component

```tsx
interface SessionChipProps {
  session: SessionSummary
  onClick?: () => void
}

function SessionChip({ session, onClick }: SessionChipProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex flex-col items-start px-2 py-1.5 rounded border",
        "hover:bg-bg-2 transition-colors",
        "min-w-[100px]"
      )}
    >
      <div className="flex items-center gap-1.5">
        <StatusDot status={session.status} />
        <span className="font-mono text-xs">{session.spawn_id}</span>
      </div>
      <span className="text-xs text-muted-foreground truncate">
        {session.agent || session.harness}
      </span>
    </button>
  )
}
```

## Session Card (Standalone)

Larger card for the quick sessions section and session list.

```
┌─────────────────────────────────────────────┐
│ ● p60                              2m ago   │
│                                             │
│ Fix that one bug in the auth flow where     │
│ the token refresh fails silently...         │
│                                             │
│ [claude] [opus-4-6]                         │
└─────────────────────────────────────────────┘
```

### Anatomy

```
┌───────────────────────────────────────────────────────┐
│ [status] [spawn_id]                      [timestamp]  │  ← Header
│                                                       │
│ [prompt_preview]                                      │  ← Body (2-3 lines)
│                                                       │
│ [harness] [model] [agent?]                            │  ← Footer badges
└───────────────────────────────────────────────────────┘
```

### Sizing

| Context | Width | Height |
|---------|-------|--------|
| Quick sessions grid | ~280px | auto (content) |
| Session list | full width | ~80px |

### States

Visual treatment by status:

| Status | Border | Background |
|--------|--------|------------|
| Running | accent border-left | subtle pulse bg |
| Idle | default border | default bg |
| Succeeded | green border-left | default bg |
| Failed | red border-left | subtle red tint |
| Cancelled | amber border-left | default bg |

### Interactions

| Action | Behavior |
|--------|----------|
| Click | Navigate to session view |
| Hover | Elevate card, show actions |
| Right-click | Context menu |

### Context Menu

- **View session** — navigate to session
- **Attach to work** — open work selector
- **Cancel** — cancel if running
- **Copy spawn ID** — copy to clipboard

### Component

```tsx
interface SessionCardProps {
  session: SessionDetail
  variant?: 'card' | 'row'
  onClick?: () => void
}

function SessionCard({ session, variant = 'card', onClick }: SessionCardProps) {
  const isRunning = session.status === 'running'
  
  return (
    <div
      onClick={onClick}
      className={cn(
        "rounded-lg border cursor-pointer transition-all",
        "hover:bg-bg-2 hover:shadow-sm",
        variant === 'card' ? "p-3" : "p-2 flex items-center gap-3",
        isRunning && "border-l-2 border-l-accent"
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <StatusDot status={session.status} />
          <span className="font-mono text-sm">{session.spawn_id}</span>
        </div>
        <RelativeTime date={session.created_at} className="text-xs text-muted" />
      </div>
      
      {variant === 'card' && (
        <p className="mt-2 text-sm text-secondary line-clamp-2">
          {session.prompt}
        </p>
      )}
      
      <div className={cn("flex gap-1.5", variant === 'card' ? "mt-2" : "ml-auto")}>
        <Badge variant="outline">{session.harness}</Badge>
        {session.model && <Badge variant="outline">{session.model}</Badge>}
        {session.agent && <Badge variant="outline">{session.agent}</Badge>}
      </div>
    </div>
  )
}
```

## Work Item Card

Container for multiple sessions under one work item.

```
┌───────────────────────────────────────────────────────────────┐
│ ● auth-middleware                                    1h ago   │
│                                                               │
│ Implement JWT validation and refresh token flow for the      │
│ API authentication layer.                                     │
│                                                               │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│ │ ● p42        │ │ ● p43        │ │ ✓ p44        │            │
│ │ orchestrator │ │ coder        │ │ reviewer     │            │
│ └──────────────┘ └──────────────┘ └──────────────┘            │
│                                                               │
│ [meridian-cli]                                                │
└───────────────────────────────────────────────────────────────┘
```

### Anatomy

```
┌───────────────────────────────────────────────────────────────┐
│ [status] [work_id]                               [timestamp]  │
│                                                               │
│ [description]                                                 │
│                                                               │
│ [session_chips...]                                            │
│                                                               │
│ [repo_badge]                                                  │
└───────────────────────────────────────────────────────────────┘
```

### Status Aggregation

Work item status is derived from child sessions:

| Condition | Work Status |
|-----------|-------------|
| Any session running | ● Running |
| All sessions terminal, any failed | ✗ Failed |
| All sessions succeeded | ✓ Completed |
| All sessions cancelled | ⊘ Cancelled |
| No sessions | ○ Empty |

### Session Chip Limit

Show at most 5 session chips. If more exist:

```
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────┐
│ ● p42        │ │ ● p43        │ │ ✓ p44        │ │ +3 more  │
│ orchestrator │ │ coder        │ │ reviewer     │ │          │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────┘
```

Clicking "+3 more" navigates to the work item detail view.

### Component

```tsx
interface WorkItemCardProps {
  workItem: WorkItemDetail
  onNavigate?: (workId: string) => void
  onSessionClick?: (sessionId: string) => void
}

function WorkItemCard({ workItem, onNavigate, onSessionClick }: WorkItemCardProps) {
  const aggregateStatus = deriveWorkStatus(workItem.sessions)
  const visibleSessions = workItem.sessions.slice(0, 5)
  const hiddenCount = workItem.sessions.length - 5
  
  return (
    <div
      className="rounded-lg border p-4 hover:bg-bg-2 cursor-pointer"
      onClick={() => onNavigate?.(workItem.work_id)}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <StatusDot status={aggregateStatus} />
          <span className="font-mono font-medium">{workItem.work_id}</span>
        </div>
        <RelativeTime date={workItem.last_activity} />
      </div>
      
      <p className="mt-2 text-sm text-secondary line-clamp-2">
        {workItem.description}
      </p>
      
      <div className="mt-3 flex flex-wrap gap-2">
        {visibleSessions.map(session => (
          <SessionChip
            key={session.session_id}
            session={session}
            onClick={(e) => {
              e.stopPropagation()
              onSessionClick?.(session.session_id)
            }}
          />
        ))}
        {hiddenCount > 0 && (
          <div className="flex items-center px-2 text-xs text-muted">
            +{hiddenCount} more
          </div>
        )}
      </div>
      
      <div className="mt-3">
        <Badge variant="secondary">{workItem.repo_name}</Badge>
      </div>
    </div>
  )
}
```

## Progress Indicators

### Running Session

Show activity indicators for running sessions:

```tsx
function StatusDot({ status }: { status: SessionStatus }) {
  if (status === 'running') {
    return (
      <span className="relative flex h-2.5 w-2.5">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500" />
      </span>
    )
  }
  
  // Other statuses...
}
```

### Session with Sub-Spawns

When a session has spawned children, show a tree indicator:

```
┌──────────────────┐
│ ● p42         🌲 │  ← Tree icon indicates children
│ orchestrator     │
└──────────────────┘
```

Clicking the tree icon or the chip navigates to the session view with the spawn tree visible.
