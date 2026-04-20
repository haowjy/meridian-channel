# Meridian App — Consolidated Design

**Version**: 2026-04-19 (work-item-centric redesign)

## Vision

A dev-tool-first web UI for AI-assisted work. Work items are the organizing principle. Simple by default, powerful when needed. One server per machine serving all roots.

---

## Target Users

1. **Primary**: Developers who want a visual interface alongside CLI workflows
2. **Secondary**: Researchers and analysts who want AI help without deep CLI knowledge

The aesthetic is VS Code / Cursor / Linear — dense, professional, keyboard-friendly. Non-technical collaborators should be able to use it, but the design optimizes for developers.

---

## Architecture

### Server Model

One server per machine (like Jupyter). User-level, not repo-level.

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser (localhost:7676)                                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Dashboard (/)  │  Session View (/s/:id)  │  Work (/w/:id)│   │
│  └──────────────────────────────────────────────────────────┘   │
│         │ REST/WS                                                │
└─────────┼────────────────────────────────────────────────────────┘
          │
┌─────────┼────────────────────────────────────────────────────────┐
│  FastAPI Server (localhost:7676)                                 │
│  ├── SessionRegistry (~/.meridian/app/sessions.jsonl)            │
│  ├── RootRegistry (~/.meridian/app/roots.jsonl)                  │
│  ├── SpawnManager (harness connections)                          │
│  ├── FileExplorer (multi-root filesystem access)                 │
│  └── WorkItemAPI (queries meridian work layer)                   │
└──────────────────────────────────────────────────────────────────┘
          │
┌─────────┴────────────────────────────────────────────────────────┐
│  Harness Runtimes                                                │
│  Claude Code (subprocess) | Codex (JSON-RPC) | OpenCode (HTTP)   │
└──────────────────────────────────────────────────────────────────┘
```

### Key Concepts

- **Session** = metadata alias mapping session_id → (project_key, spawn_id, repo_root, work_id)
- **Work Item** = first-class grouping of related sessions
- **Root** = registered filesystem root for the file explorer
- **Spawn** = Meridian run identity, the actual harness process

---

## UI Layout

Three-section layout: activity bar + sidebar + main pane. Desktop-first.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ┌────────┬─────────────────────┬─────────────────────────────────────────────┤
│ │        │  WORK         [+]   │                                             │
│ │ [🏠]   │                     │  Active Work                                │
│ │ [📁]   │  ▼ ● auth-middleware│  ┌───────────────────────────────────────┐  │
│ │ [⚡]   │      ● p42 orch   2m│  │ ● auth-middleware              1h ago │  │
│ │        │      ● p43 coder  5m│  │   Implement JWT validation...         │  │
│ │        │      ✓ p44 rev   10m│  │   [● p42] [● p43] [✓ p44]             │  │
│ │        │                     │  └───────────────────────────────────────┘  │
│ │        │  ▶ ○ spawn-tree-view│                                             │
│ │        │                     │  Quick Sessions                             │
│ │        │  ─────────────────  │  ┌──────────┐ ┌──────────┐                  │
│ │        │  QUICK              │  │ ○ p60    │ │ ✓ p55    │                  │
│ │        │    ○ p60 Fix...  2m │  │ Fix bug  │ │ Syntax?  │                  │
│ │        │    ✓ p55 What... 1h │  └──────────┘ └──────────┘                  │
│ │ ────── │                     │                                             │
│ │ [⚙]   │                     │  ┌───────────────────────────────────────┐  │
│ │        │                     │  │ What would you like to work on?       │  │
│ │        │                     │  │ ┌─────────────────────────────────┐   │  │
│ │        │                     │  │ │                                 │   │  │
│ │        │                     │  │ └─────────────────────────────────┘   │  │
│ │        │                     │  │ [Quick ○ ● Thorough]   [Adv ▾] [Send] │  │
│ └────────┴─────────────────────┴─────────────────────────────────────────────┤
│                                                              Status Bar      │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Layout Components

| Component | Width | Purpose |
|-----------|-------|---------|
| Activity Bar | 48px | Top-level navigation icons |
| Sidebar | 264px | Work items + sessions list |
| File Explorer | 200-400px | Multi-root file tree (collapsible panel) |
| Main Pane | flex-1 | Primary content area |
| Status Bar | 100% | Connection status, session info |

---

## Routes

| Path | Component | Purpose |
|------|-----------|---------|
| `/` | Dashboard | Work-item-centric dashboard |
| `/s/:sessionId` | SessionView | Thread view for one session |
| `/w/:workId` | WorkItemView | Detail view for work item |
| `/sessions` | AllSessionsView | All sessions (filterable) |
| `/settings` | Settings | App configuration |
| `*` | Redirect → `/` | Unknown paths |

Router: **wouter** (~1.5kb)

---

## Component Hierarchy

```
App.tsx
├── ActivityBar               ← Left icon bar (48px)
├── Sidebar                   ← Work-item-grouped sessions (264px)
│   ├── SidebarHeader
│   ├── WorkSection
│   │   ├── WorkItemGroup
│   │   └── SessionRow
│   └── QuickSection
├── FileExplorer             ← Multi-root tree (collapsible)
│   ├── ExplorerHeader
│   ├── RootNode
│   └── TreeNode
├── MainPane                 ← Route container
│   ├── Dashboard            ← Route: /
│   ├── SessionView          ← Route: /s/:sessionId
│   ├── WorkItemView         ← Route: /w/:workId
│   └── Settings             ← Route: /settings
└── StatusBar                ← Footer
```

See detailed component specs in:
- `dashboard-layout.md`
- `sidebar.md`
- `file-explorer.md`
- `session-cards.md`

---

## Composer

### Dashboard Composer (New Session)

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  What would you like to work on?                                │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  [Textarea]                                                     │
├─────────────────────────────────────────────────────────────────┤
│  [Quick ○ ● Thorough]                   [Advanced ▾]    [Send]  │
└─────────────────────────────────────────────────────────────────┘
```

**Effort Toggle**: Quick (fast, cheaper) vs Thorough (deeper thinking). Default: Thorough.

**Advanced Panel** (collapsed by default):
- Harness selector (claude/codex/opencode)
- Model dropdown
- Agent profile dropdown
- Work item attachment (existing or new)

### Session Composer (Active Session)

```
┌─────────────────────────────────────────────────────────────────┐
│  Continue your conversation...                                  │
├─────────────────────────────────────────────────────────────────┤
│                                      [Model: Opus ▾]    [Send]  │
└─────────────────────────────────────────────────────────────────┘
```

Mid-session controls shown based on harness capabilities.

---

## API Endpoints

### Sessions

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/sessions` | List sessions (filter by work_id, unattached) |
| POST | `/api/sessions` | Create session |
| GET | `/api/sessions/:id` | Get session detail |
| PATCH | `/api/sessions/:id` | Update (work attachment) |
| DELETE | `/api/sessions/:id` | Cancel session |
| WS | `/api/sessions/:id/ws` | Stream events |
| GET | `/api/sessions/:id/tree` | Get spawn tree |

### Work Items

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/work-items` | List work items with sessions |
| GET | `/api/work-items/:id` | Get work item detail |

### File Explorer

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/explorer/roots` | List registered roots |
| POST | `/api/explorer/roots` | Add root |
| DELETE | `/api/explorer/roots` | Remove root |
| GET | `/api/explorer/list` | List directory contents |
| GET | `/api/explorer/read` | Read file content |

### Sidebar

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/sidebar` | Optimized sidebar data (work items + quick sessions) |

---

## Harness Control Matrix

| Capability | Claude | Codex | OpenCode |
|------------|--------|-------|----------|
| Model switch | `/model` (may need restart) | `thread/start` RPC | Per-message `model?` |
| Effort | Launch only | `thread/resume` RPC | Unsupported |
| Skills | `/skill-name` text | `skills/config/write` RPC | `/agent` |
| Compact | `/compact` text | `thread/compact/start` RPC | `/summarize` |
| Interrupt | SIGINT | `turn/interrupt` RPC | `/abort` |

See `HARNESS-CONTROL-MATRIX.md` for details.

---

## Scope

### MVP (Phase 1)

- Dashboard with work-item-centric organization
- Session view with thread
- Sidebar with work-grouped sessions
- File explorer (multi-root)
- Effort toggle
- Basic harness/model selection
- Session persistence

### Phase 2

- Mid-session model switching
- Skill activation UI
- Compact button
- Session spawn tree visualization
- File attachment to composer

### Phase 3

- Event replay for completed sessions
- Remote access with auth
- Server model abstraction for cloud

### Out of Scope (v1)

- Mobile-first design
- Rich model cards
- Real-time collaboration
- Cloud backend

---

## Tech Stack

- **Frontend**: React 19, Radix UI, Tailwind, wouter, Lucide icons
- **Backend**: FastAPI, WebSocket, AG-UI protocol
- **State**: Server-side JSONL files, client React state (SWR/React Query)
- **Build**: pnpm, Vite

---

## Design Documents

| Document | Purpose |
|----------|---------|
| `visual-direction.md` | Color, typography, spacing, interaction patterns |
| `dashboard-layout.md` | Work-item-centric dashboard design |
| `sidebar.md` | Sidebar with work-grouped sessions |
| `session-cards.md` | Session and work item card components |
| `file-explorer.md` | Multi-root file explorer |
| `frontend-routing.md` | Routes and component structure |
| `session-registry.md` | Session storage and API |
| `server-abstraction.md` | Future cloud swappability |
| `HARNESS-CONTROL-MATRIX.md` | Per-harness capabilities |
| `server-lifecycle.md` | Server start/stop |
| `project-key.md` | Project identity |
