# Frontend UI Redesign

## Problem

The current app is a single-page form-to-thread flow: SpawnSelector (harness dropdown + prompt textarea) transitions to ThreadView + Composer when a spawn is created. There's no session persistence, no navigation, no way to switch between conversations, and the spawn configuration UI is a basic HTML form. This design transforms the app into a session-based chat interface with persistent sidebar navigation and rich composer controls.

## Relationship to Other Design Docs

This doc covers the **frontend UX architecture** — layout, component design, interaction patterns, and visual design. It builds on top of:

- **[session-registry.md](session-registry.md)** — backend session API endpoints (`GET/POST /api/sessions`, `WS /api/sessions/{sid}/ws`)
- **[frontend-routing.md](frontend-routing.md)** — wouter routing setup, SPA fallback, `SessionView` component extraction
- **[overview.md](overview.md)** — server architecture, URL scheme, multi-repo model

Where this doc conflicts with frontend-routing.md, this doc takes precedence — the routing doc describes a Dashboard-centric layout; this doc replaces that with a sidebar-centric layout.

## Layout Architecture

The app uses a two-column layout: persistent sidebar + main pane. The sidebar is always visible (no responsive collapse for v1 — desktop-first per requirements).

```
┌──────────────────────────────────────────────────────────────────┐
│ App Shell (100vh, flex row)                                      │
│                                                                  │
│ ┌───────────────┬────────────────────────────────────────────────┐│
│ │  Sidebar      │  Main Pane                                    ││
│ │  (280px,      │  (flex-1)                                     ││
│ │   fixed)      │                                               ││
│ │               │  ┌────────────────────────────────────────┐   ││
│ │  [+ New Chat] │  │                                        │   ││
│ │               │  │  Route: /                              │   ││
│ │  Today        │  │    EmptyState (logo + tagline)         │   ││
│ │   ● session 1 │  │                                        │   ││
│ │   ○ session 2 │  │  Route: /s/:sessionId                  │   ││
│ │               │  │    SessionHeader                       │   ││
│ │  Yesterday    │  │    ThreadView (existing)               │   ││
│ │   ✓ session 3 │  │    StreamingIndicator (existing)       │   ││
│ │               │  │                                        │   ││
│ │               │  ├────────────────────────────────────────┤   ││
│ │               │  │  Composer                              │   ││
│ │               │  │  [controls row]                        │   ││
│ │               │  │  [textarea]                            │   ││
│ │               │  │  [action buttons]                      │   ││
│ │               │  └────────────────────────────────────────┘   ││
│ │               │                                               ││
│ │  ─────────    │                                               ││
│ │  [theme] [⚙]  │                                               ││
│ └───────────────┴────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────┘
```

Key layout decisions:

- **No top header bar.** The current `<header>` with "meridian" + badges is removed. The sidebar header carries the branding. Session-specific metadata moves to `SessionHeader` inside the main pane.
- **No bottom StatusBar.** Connection status moves into the `SessionHeader`. The StatusBar component is retired.
- **Sidebar width**: 280px, fixed. Not resizable in v1.
- **Main pane**: `flex-1`, fills remaining width. Content is max-width constrained (5xl / 64rem) and centered, matching the current layout.

## Component Hierarchy

```
App.tsx                              ← Shell: sidebar + router
├── Sidebar                          ← Persistent left column
│   ├── SidebarHeader                ← Logo + "New Chat" button
│   ├── SessionList                  ← Grouped session items
│   │   ├── SessionGroup             ← "Today", "Yesterday", etc.
│   │   │   └── SessionItem[]        ← Clickable session entries
│   │   └── SessionGroup...
│   └── SidebarFooter                ← Theme toggle, settings
├── MainPane                         ← Route-dependent content
│   ├── EmptyState                   ← Route: / (no active session)
│   │   ├── Logo + tagline
│   │   └── Composer                 ← Can start typing immediately
│   └── SessionView                  ← Route: /s/:sessionId
│       ├── SessionHeader            ← Harness, model, status, connection
│       ├── ThreadView               ← Existing activity stream
│       ├── StreamingIndicator       ← Existing
│       └── Composer                 ← Enhanced with controls
│           ├── ComposerControls     ← Control row above textarea
│           │   ├── HarnessToggle    ← 3 icon tabs
│           │   ├── ModelButton      ← Opens ModelBrowser
│           │   ├── EffortSelector   ← Segmented control
│           │   └── AgentSelector    ← Profile dropdown
│           ├── ComposerTextarea     ← Existing auto-resize textarea
│           └── ComposerActions      ← Send / Interrupt / Cancel
└── ModelBrowser                     ← Dialog overlay (portal)
    ├── HarnessTabStrip              ← Left sidebar within dialog
    └── ModelGrid                    ← Scrollable model cards
        └── ModelCard[]
```

## File Structure

New and modified files:

```
frontend/src/
├── App.tsx                              ← Rewrite: shell with sidebar + router
├── features/
│   ├── sidebar/                         ← NEW
│   │   ├── Sidebar.tsx                  ← Container: header + list + footer
│   │   ├── SidebarHeader.tsx            ← Logo + new chat button
│   │   ├── SessionList.tsx              ← Grouped list with polling
│   │   ├── SessionItem.tsx              ← One session row
│   │   └── SidebarFooter.tsx            ← Theme toggle
│   ├── empty-state/                     ← NEW
│   │   └── EmptyState.tsx               ← Landing page content
│   ├── session/                         ← NEW (absorbs spawn-selector logic)
│   │   ├── SessionView.tsx              ← Route component for /s/:id
│   │   └── SessionHeader.tsx            ← Replaces SpawnHeader
│   ├── threads/
│   │   ├── composer/
│   │   │   ├── Composer.tsx             ← MODIFY: add controls row
│   │   │   ├── ComposerControls.tsx     ← NEW: harness + model + effort + agent
│   │   │   ├── HarnessToggle.tsx        ← NEW: 3 icon toggle group
│   │   │   ├── ModelButton.tsx          ← NEW: compact model display + click
│   │   │   ├── EffortSelector.tsx       ← NEW: segmented control
│   │   │   ├── AgentSelector.tsx        ← NEW: profile dropdown
│   │   │   └── CapabilityBadge.tsx      ← Existing
│   │   └── components/
│   │       ├── ThreadView.tsx           ← Unchanged
│   │       └── StreamingIndicator.tsx   ← Unchanged
│   ├── model-browser/                   ← NEW
│   │   ├── ModelBrowser.tsx             ← Dialog with harness tabs + grid
│   │   ├── ModelCard.tsx                ← Individual model display
│   │   └── HarnessTabStrip.tsx          ← Vertical harness selector in dialog
│   ├── activity-stream/                 ← Unchanged
│   └── spawn-selector/                  ← RETIRE (functionality moves to Composer)
│       ├── SpawnSelector.tsx            ← Remove
│       └── SpawnHeader.tsx              ← Remove (replaced by SessionHeader)
├── hooks/
│   ├── use-thread-streaming.ts          ← MODIFY: sessionId instead of spawnId
│   ├── use-session-list.ts              ← NEW: fetch + poll sessions
│   ├── use-model-catalog.ts             ← NEW: fetch models from API
│   └── use-agent-profiles.ts            ← NEW: fetch agent profiles from API
└── lib/
    ├── ws/
    │   ├── spawn-channel.ts             ← MODIFY: session-based WS URL
    │   └── ...                          ← Unchanged
    └── utils.ts                         ← Unchanged
```

## Routing

Uses wouter (new dependency: `pnpm add wouter`).

| Path | Component | Content |
|------|-----------|---------|
| `/` | `EmptyState` + `Composer` | Logo, tagline, composer ready for input |
| `/s/:sessionId` | `SessionView` | Thread + composer for active/completed session |
| `*` | Redirect to `/` | Unknown paths |

The sidebar renders at every route. Only the main pane content changes.

```tsx
// App.tsx (simplified)
function App() {
  return (
    <TooltipProvider>
      <div className="flex h-screen bg-background text-foreground">
        <Sidebar />
        <main className="flex min-w-0 flex-1 flex-col">
          <Switch>
            <Route path="/" component={LandingPage} />
            <Route path="/s/:sessionId" component={SessionView} />
            <Route><Redirect to="/" /></Route>
          </Switch>
        </main>
      </div>
    </TooltipProvider>
  )
}
```

`LandingPage` is a thin wrapper that renders `EmptyState` + `Composer` together. The Composer on the landing page creates a new session on submit and navigates to `/s/{sessionId}`.

## Sidebar

### SidebarHeader

Compact branding area at the top:

```
┌───────────────┐
│ ◆ meridian    │   ← logo icon + wordmark, font-mono
│               │
│ [+ New Chat]  │   ← full-width button, outline variant
└───────────────┘
```

"New Chat" navigates to `/` (the landing page with empty state + composer). If already on `/`, it's a no-op (button appears muted/disabled).

### SessionList

Fetched from `GET /api/sessions`. Polled every 5 seconds while the sidebar is mounted. Sessions grouped by recency:

| Group | Rule |
|-------|------|
| Today | `created_at` is today |
| Yesterday | `created_at` is yesterday |
| Previous 7 Days | Within last 7 days |
| Older | Everything else |

Groups are rendered as collapsible sections with muted headings. Empty groups are hidden.

### SessionItem

Each item in the list:

```
┌───────────────┐
│ ● Fix the lo… │   ← status dot + prompt preview (truncated)
│   claude · 2m │   ← harness name + relative time
└───────────────┘
```

**Status indicators:**
- `●` green pulse — running (spawn is active)
- `✓` muted — succeeded
- `✗` destructive — failed
- `○` muted — cancelled

**Active state:** The session matching the current URL (`/s/:sessionId`) gets a highlighted background (`bg-accent`). This is derived from the route, not from click state.

**Click:** Navigates to `/s/{sessionId}` via wouter's `useLocation`.

**Prompt preview:** First ~60 characters of the session's prompt, truncated with ellipsis. Shown as the primary text.

**Secondary line:** Harness name (lowercase) + relative timestamp (`2m`, `1h`, `3d`).

### SidebarFooter

Minimal footer pinned to the bottom of the sidebar:

```
┌───────────────┐
│ [moon/sun] [⚙]│   ← theme toggle, future settings
└───────────────┘
```

Theme toggle uses the existing `ThemeProvider` context. Just a moon/sun icon button that cycles through light → dark → system.

## Empty State (Landing Page)

When no session is active (route `/`):

```
┌──────────────────────────────────────────────────┐
│                                                  │
│                                                  │
│                                                  │
│                    ◆                             │
│                                                  │
│                meridian                           │   ← font-mono, text-2xl
│                                                  │
│        Multi-agent coordination                  │   ← text-muted-foreground
│        for software engineering                  │
│                                                  │
│                                                  │
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │ [claude | codex | opencode] [model] ...  │    │
│  │                                          │    │
│  │ What would you like to work on?          │    │
│  │                                          │    │
│  │                                [Send >]  │    │
│  └──────────────────────────────────────────┘    │
└──────────────────────────────────────────────────┘
```

The logo and tagline are vertically centered in the available space above the composer. The composer is pinned to the bottom of the main pane (same position as in a session view). This means the empty state content and composer together fill the main pane, with the text content centered in the upper area.

The Composer on the landing page is fully functional — all controls (harness, model, effort, agent) are available. Submitting creates a new session via `POST /api/sessions` and navigates to `/s/{sessionId}`.

## Composer Controls

The composer expands from the current simple textarea+buttons to include a controls row above the input:

```
┌────────────────────────────────────────────────────────────────┐
│  [Claude | Codex | OC]  [claude-opus-4-6 v]  [Med v]  [---]  │   ← controls row
│                                                                │
│  Describe what you'd like to work on...                        │   ← textarea
│                                                                │
│  Enter to send · Shift+Enter newline           [Cancel] [Send] │   ← actions
└────────────────────────────────────────────────────────────────┘
```

### HarnessToggle

Three icon buttons in a `ToggleGroup` (existing shadcn component). Each represents a harness:

| Harness | Icon | Label |
|---------|------|-------|
| Claude | Sparkles (lucide) | `claude` |
| Codex | Terminal (lucide) | `codex` |
| OpenCode | Cpu (lucide) | `opencode` |

The toggle is `type="single"` with a required value — exactly one harness is always selected. Default: `claude`.

Selecting a harness:
1. Updates the model selector to show models for that harness
2. Clears the current model selection (since models are harness-specific)
3. Does NOT change the effort or agent selection

Size: `sm` variant. Compact enough to sit in a row with other controls.

**After session starts:** The harness toggle becomes read-only (visually muted, non-interactive). The harness is fixed for the lifetime of a session.

### ModelButton

A compact button that shows the currently selected model. Clicking opens the `ModelBrowser` dialog.

States:
- **No model selected:** Shows "Model" in muted text with a ChevronDown icon
- **Model selected:** Shows model display name (e.g., "Opus 4.6") with a small harness-colored dot

The button uses the `outline` variant, `sm` size. It sits inline with the other controls.

**After session starts:** The model button becomes read-only (shows the model but is not clickable). The model is fixed for the session.

### EffortSelector

A segmented control with 4 levels. Uses a `ToggleGroup` with `type="single"`:

| Level | Label | Description |
|-------|-------|-------------|
| `low` | Lo | Minimal thinking, fast responses |
| `medium` | Med | Balanced (default) |
| `high` | Hi | Deep thinking, thorough responses |
| `max` | Max | Maximum effort, slowest |

Default: `medium`.

**Effort is changeable mid-session.** Unlike harness/model/agent, the effort level can be adjusted at any time. Changing effort mid-session sends the appropriate command via the effort injection endpoint.

Effort-to-harness mapping (sent at session creation as a `SpawnParams.effort` value, and mid-session via `POST /api/sessions/{sid}/effort`):

| Level | Claude | Codex |
|-------|--------|-------|
| low | `budget_tokens=1024` | `effort=low` |
| medium | `budget_tokens=10240` | `effort=medium` |
| high | `budget_tokens=32768` | `effort=high` |
| max | no budget limit | `effort=max` |

The exact mapping values are harness-adapter concerns — the frontend sends the level string, the backend maps it.

### AgentSelector

A `Select` (existing shadcn component) showing available agent profiles. Data from `GET /api/agents`.

States:
- **No agent selected:** Shows "No agent" placeholder. This is valid — sessions can run without an agent profile.
- **Agent selected:** Shows agent name.

The select items show:
```
┌─────────────────────────┐
│ coder                   │   ← agent name
│ Production code writer  │   ← description (muted, truncated)
├─────────────────────────┤
│ reviewer                │
│ Code review specialist  │
├─────────────────────────┤
│ ...                     │
└─────────────────────────┘
```

**After session starts:** The agent selector becomes disabled (locked). Agent profiles set the system prompt and skills at session creation — changing mid-session is not supported.

### Composer State Machine

The controls have two modes based on session state:

**Pre-session (empty state / new chat):** All controls are interactive. Submitting the composer creates a session with the selected harness, model, effort, and agent.

**Active session:** Harness, model, and agent are locked (read-only display). Effort remains changeable. The textarea and action buttons work as they do today (send, interrupt, cancel based on capabilities).

```
Controls state:
┌─────────────────────────────────────────────────┐
│              Pre-session    Active session       │
│ Harness      interactive    locked (display)     │
│ Model        interactive    locked (display)     │
│ Effort       interactive    interactive          │
│ Agent        interactive    locked (display)     │
│ Textarea     interactive    interactive          │
│ Send         interactive    interactive          │
└─────────────────────────────────────────────────┘
```

## Model Browser

The model browser is a `Dialog` (existing shadcn component) that opens when the user clicks the ModelButton. It provides a browsable catalog of available models.

```
┌──────────────────────────────────────────────────────────────┐
│  Select a Model                                         [x]  │
│                                                              │
│  ┌────────┬─────────────────────────────────────────────────┐│
│  │        │                                                 ││
│  │  Claude│  ┌─────────────────┐  ┌─────────────────┐      ││
│  │        │  │ Opus 4.6         │  │ Sonnet 4.6       │     ││
│  │  Codex │  │ claude-opus-4-6  │  │ claude-sonnet-4-6│     ││
│  │        │  │ $$$              │  │ $$               │     ││
│  │  OC    │  │ 200K ctx · 32K  │  │ 200K ctx · 64K   │     ││
│  │        │  │ tool_call vision │  │ tool_call vision  │     ││
│  │        │  └─────────────────┘  └─────────────────┘      ││
│  │        │                                                 ││
│  │        │  ┌─────────────────┐  ┌─────────────────┐      ││
│  │        │  │ Haiku 4.5        │  │ Sonnet 4.5       │     ││
│  │        │  │ claude-haiku-4-5 │  │ claude-sonnet-4-5│     ││
│  │        │  │ $                │  │ $$               │     ││
│  │        │  │ 200K ctx · 8K   │  │ 200K ctx · 64K   │     ││
│  │        │  └─────────────────┘  └─────────────────┘      ││
│  │        │                                                 ││
│  └────────┴─────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────┘
```

### Layout

- **Dialog size:** `max-w-3xl`, `max-h-[70vh]`
- **Left strip:** ~80px wide, vertical stack of 3 harness icons. The active harness has a highlighted background. Clicking a harness icon switches the model grid.
- **Right area:** Scrollable grid of model cards. 2 columns on wide screens, 1 column if dialog is narrow.

### ModelCard

Each card is a clickable `Card` component:

```
┌─────────────────────┐
│ Opus 4.6            │   ← display name (name field, or derived from model_id)
│ claude-opus-4-6     │   ← model_id, font-mono, text-xs, muted
│                     │
│ $$$  200K ctx  32K  │   ← cost_tier · context_limit · output_limit
│                     │
│ [tool_call] [vision]│   ← capability badges
│                     │
│ Most capable model  │   ← description (if available), text-xs, muted
│ for complex tasks   │
└─────────────────────┘
```

**Hover:** Subtle border highlight (`ring-1 ring-accent-fill/40`).

**Click:** Selects the model, updates the Composer state, closes the dialog.

**Currently selected model:** If the user already has a model selected and reopens the browser, that model's card has a persistent highlight (`ring-2 ring-accent-fill`).

### Data Source

Models come from `GET /api/models` (new endpoint, see Backend section). The hook `useModelCatalog()` fetches once and caches — the model list doesn't change during a session. The response includes all fields from `CatalogModel`.

The model list is pre-filtered to exclude superseded models (the API handles this, matching `meridian models list` default behavior without `--show-superseded`).

### Harness-Model Synchronization

When the user picks a model from harness X in the browser, the HarnessToggle in the composer updates to X. Conversely, switching the harness toggle in the composer pre-selects that harness tab in the browser (if opened). This is a natural consequence of both reading from the same `harness` state.

## Session View

`SessionView` is the route component for `/s/:sessionId`. It absorbs the session-specific logic currently in `App.tsx`.

```tsx
function SessionView({ params }: { params: { sessionId: string } }) {
  const sessionId = params.sessionId

  // Load session metadata (harness, model, agent, status, repo)
  const session = useSessionMetadata(sessionId)

  // Connect to WebSocket stream
  const { state, capabilities, channel, cancel, connectionState } =
    useThreadStreaming(sessionId)

  // Session is "locked" — controls are read-only
  const isSessionActive = session?.status === "running"

  return (
    <div className="flex h-full flex-col">
      <SessionHeader session={session} connectionState={connectionState} />
      <div className="min-h-0 flex-1">
        <ThreadView items={state.items} error={state.error} />
      </div>
      {state.isStreaming ? <StreamingIndicator /> : null}
      <Composer
        channel={channel}
        capabilities={capabilities}
        isStreaming={state.isStreaming}
        disabled={!isSessionActive || connectionState !== "open"}
        onCancel={cancel}
        // Locked config from session
        harness={session?.harness}
        model={session?.model}
        agent={session?.agent}
        locked={true}
      />
    </div>
  )
}
```

### SessionHeader

Replaces `SpawnHeader`. Shows session metadata in a compact bar:

```
┌──────────────────────────────────────────────────────────────┐
│  * claude  ·  claude-opus-4-6  ·  coder        ● connected   │
└──────────────────────────────────────────────────────────────┘
```

Elements:
- Harness icon + name
- Model ID (mono)
- Agent name (if any)
- Connection status dot + label (same styling as current StatusBar)
- CapabilityBadge (existing — shows Queue/Steer/Direct messaging mode)

For completed sessions, the connection area shows the terminal status (`succeeded`, `failed`, `cancelled`) instead of a live connection indicator.

## Hooks

### useSessionList

```tsx
function useSessionList(): {
  sessions: SessionListEntry[]
  isLoading: boolean
  error: string | null
}
```

- Fetches `GET /api/sessions` on mount
- Polls every 5 seconds while mounted
- Returns sessions in reverse chronological order
- Cleans up interval on unmount

```tsx
interface SessionListEntry {
  session_id: string
  spawn_id: string
  repo_root: string
  repo_name: string
  harness: string
  model: string | null
  agent: string | null
  status: "running" | "succeeded" | "failed" | "cancelled"
  created_at: string
  prompt: string  // truncated server-side
}
```

### useSessionMetadata

```tsx
function useSessionMetadata(sessionId: string | null): {
  session: SessionDetail | null
  isLoading: boolean
  error: string | null
}
```

- Fetches `GET /api/sessions/{sessionId}` on mount
- Returns full session detail (same as list entry + capabilities)
- Re-fetches when `sessionId` changes

### useModelCatalog

```tsx
function useModelCatalog(): {
  models: CatalogModel[]
  byHarness: Map<string, CatalogModel[]>
  isLoading: boolean
  error: string | null
}
```

- Fetches `GET /api/models` once on mount
- Groups models by harness in `byHarness` for the ModelBrowser
- No polling — model list is static

```tsx
interface CatalogModel {
  model_id: string
  harness: string
  name: string | null
  family: string | null
  provider: string | null
  cost_tier: string | null      // "$", "$$", "$$$"
  context_limit: number | null  // tokens
  output_limit: number | null   // tokens
  capabilities: string[]        // ["tool_call", "vision", ...]
  description: string | null
  aliases: string[]
}
```

### useAgentProfiles

```tsx
function useAgentProfiles(): {
  agents: AgentProfileSummary[]
  isLoading: boolean
  error: string | null
}
```

- Fetches `GET /api/agents` once on mount
- Returns summary info for the selector

```tsx
interface AgentProfileSummary {
  name: string
  description: string
  model: string | null
  harness: string | null
}
```

### useThreadStreaming Changes

The existing hook changes its addressing from `spawnId` to `sessionId`:

```tsx
// Before
export function useThreadStreaming(spawnId: string | null)
// WS URL: /api/spawns/{spawnId}/ws

// After
export function useThreadStreaming(sessionId: string | null)
// WS URL: /api/sessions/{sessionId}/ws
```

The `SpawnChannel` class updates its URL builder accordingly. The protocol (AG-UI events, control messages) is unchanged.

## Session Creation Flow

When the user submits the Composer from the empty state:

1. Composer collects: `harness`, `model`, `effort`, `agent`, `prompt`
2. `POST /api/sessions` with:
   ```json
   {
     "harness": "claude",
     "prompt": "Fix the login bug...",
     "model": "claude-opus-4-6",
     "agent": "coder",
     "effort": "medium",
     "repo_root": "/home/user/my-project"
   }
   ```
3. Response returns `{ session_id, spawn_id, ... }`
4. Navigate to `/s/{session_id}` via wouter's `useLocation`
5. `SessionView` mounts, reads sessionId from params
6. `useThreadStreaming(sessionId)` opens WebSocket
7. Sidebar poll picks up the new session within 5 seconds

### Repo Root Resolution

The `repo_root` is determined by the server's launch context. When `meridian app` is invoked from a repo directory, the server knows its repo_root. For v1 (single-repo), the frontend does not need a repo selector — the backend uses the server's repo_root for all session creation.

Multi-repo support (repo selector in the composer, dashboard grouping by repo) is designed in the session-registry doc but deferred for the UI. The frontend simply omits `repo_root` from the POST request, and the backend uses its default.

## New Backend Endpoints

Three new REST endpoints beyond those in session-registry.md:

### `GET /api/models` — Model Catalog

Returns available models for the model browser.

```python
@app.get("/api/models")
async def list_models():
    from meridian.lib.ops.catalog import models_list_sync, ModelsListInput
    result = models_list_sync(ModelsListInput(show_all=False, show_superseded=False))
    return {"models": [m.model_dump() for m in result.models]}
```

Response shape matches `CatalogModel` from `src/meridian/lib/ops/catalog.py`. Fields: `model_id`, `harness`, `name`, `family`, `provider`, `cost_tier`, `context_limit`, `output_limit`, `capabilities`, `description`, `aliases`.

Caching: The endpoint can compute this on every call (it's fast — reads from a local cache file). No server-side caching needed.

### `GET /api/agents` — Agent Profiles

Returns available agent profiles for the agent selector.

```python
@app.get("/api/agents")
async def list_agents():
    from meridian.lib.catalog.agent import scan_agent_profiles
    profiles = scan_agent_profiles(repo_root=repo_root)
    return {
        "agents": [
            {
                "name": p.name,
                "description": p.description,
                "model": p.model,
                "harness": p.harness,
            }
            for p in profiles
        ]
    }
```

Returns summary fields only — the full agent body (system prompt) is not sent to the frontend.

### `POST /api/sessions/{session_id}/effort` — Set Effort Level

Changes the effort/thinking level for an active session.

```python
@app.post("/api/sessions/{session_id}/effort")
async def set_effort(session_id: str, body: EffortRequest):
    session = session_registry.get(session_id)
    if not session:
        raise HTTPException(404)

    # Map effort level to harness-specific command
    command = map_effort_to_command(session.harness, body.level)

    # Inject via control socket
    result = await spawn_manager.inject(
        session.spawn_id,
        command,
        source="app_effort",
    )
    return {"ok": result.success}
```

Request: `{ "level": "low" | "medium" | "high" | "max" }`

The `map_effort_to_command()` function is a harness adapter concern. It translates effort levels to harness-specific slash commands or configuration changes. This mapping lives in the harness adapter layer, not in the API handler.

### Session Creation Changes

The existing `POST /api/sessions` (from session-registry.md) gains two new optional fields in the request body:

```python
class SessionCreateRequest:
    harness: str
    prompt: str
    model: str | None = None
    agent: str | None = None
    effort: str | None = None       # NEW — passed to SpawnParams.effort
    repo_root: str | None = None    # From session-registry.md
```

The `effort` field is passed through to `SpawnParams.effort`, which the harness adapter uses at spawn creation time.

## State Flow Diagram

```
                    Landing Page (/)
                    ┌──────────────┐
                    │  EmptyState  │
                    │  + Composer  │
                    └──────┬───────┘
                           │ submit (creates session)
                           │ POST /api/sessions
                           ▼
                    navigate(/s/{id})
                           │
                           ▼
                    SessionView (/s/:id)
                    ┌──────────────┐
                    │  Header      │
                    │  ThreadView  │◄── WS /api/sessions/{id}/ws
                    │  Composer    │──► inject / interrupt / cancel
                    └──────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
    spawn succeeds   spawn fails     user cancels
    status: succeeded status: failed  status: cancelled
    (terminal view)  (terminal view)  (terminal view)

Sidebar (always visible):
    useSessionList() ──► GET /api/sessions (poll 5s)
    click session    ──► navigate(/s/{id})
    + New Chat       ──► navigate(/)
```

## What Changes vs. Current App

| Aspect | Current | After |
|--------|---------|-------|
| Layout | Single column, top header + footer | Two-column: sidebar + main pane |
| Navigation | None — state toggle | wouter: `/` and `/s/:id` |
| Session persistence | None — refresh loses everything | Sessions persist via registry |
| Harness selection | Radix Select dropdown | Toggle group with icons |
| Model selection | None (hardcoded/default) | Model browser dialog with cards |
| Effort control | None | Segmented control (lo/med/hi/max) |
| Agent selection | None | Profile dropdown from .agents/ |
| Spawn creation | SpawnSelector card form | Composer on landing page |
| Branding | Top header bar | Sidebar header |
| Status display | StatusBar footer + SpawnHeader | SessionHeader (inline) |

## What Does NOT Change

- **Activity stream** — TextItem, ReasoningItem, ToolCallItem, ToolResultItem, ErrorItem all unchanged
- **Streaming reducer** — state machine, event handling, ActivityItem types
- **WebSocket protocol** — AG-UI events, control messages (user_message, interrupt, cancel)
- **WsClient** — generic WebSocket transport with reconnect
- **Theme system** — OKLCH colors, light/dark/system, CSS variables
- **UI component library** — all shadcn/ui components reused as-is
- **ThreadView** — scroll area, auto-scroll, item rendering
- **Composer core UX** — textarea auto-resize, Enter to send, Shift+Enter newline, interrupt/cancel buttons

## Dependencies

New: `wouter` (~1.5kb gzipped) — add via `pnpm add wouter`.

No other new dependencies. The model browser, harness toggle, effort selector, and agent selector are all built from existing shadcn/ui primitives (Dialog, ToggleGroup, Select, Card).

## Edge Cases & Failure Modes

### Session Creation Failures

| Scenario | Behavior |
|----------|----------|
| Network error during `POST /api/sessions` | Composer shows inline error below textarea. Controls remain unlocked so the user can retry. No navigation occurs. |
| Server returns 400 (bad harness, empty prompt) | Composer shows the error detail from the response. Same retry UX. |
| Server returns 503 (draining/shutting down) | Composer shows "Server is shutting down" message. All controls disabled. |
| Spawn starts but session JSONL write fails (500) | Backend compensates by stopping the orphaned spawn. Frontend shows generic error. |
| User submits while a prior submit is in-flight | Submit button is disabled during the request (existing `isSubmitting` guard). Prevents double-creation. |

### WebSocket Connection Failures

| Scenario | Behavior |
|----------|----------|
| WS fails to connect on session load | SessionHeader shows "disconnected" status. ThreadView shows empty state with "Could not connect to session" message. Composer disabled. |
| WS closes unexpectedly mid-stream | SessionHeader transitions to "disconnected". StreamingIndicator disappears. Items rendered so far remain visible. Composer disabled. No auto-reconnect (spawns are ephemeral — reconnecting to a finished spawn is meaningless). |
| Second tab opens same session URL | Second tab receives "another client is already connected" via WS and falls back to metadata-only view with a banner explaining the limitation. |
| Navigate to session that doesn't exist | `GET /api/sessions/{id}` returns 404. SessionView shows "Session not found" with a link back to landing page. |
| Navigate to completed session | SessionHeader shows terminal status badge (succeeded/failed/cancelled). No WS connection attempted. Thread area shows "Session completed" with metadata. Future: event replay from output.jsonl. |

### Sidebar Edge Cases

| Scenario | Behavior |
|----------|----------|
| Session list API returns empty | Sidebar shows no sessions. "New Chat" button is the only interactive element. |
| Session list poll fails (network error) | Silently retry on next 5-second interval. Last successful list remains displayed. No error UI for transient poll failures. |
| Very many sessions (100+) | SessionList uses `ScrollArea` (existing component). Groups collapse by default for older time ranges ("Previous 7 Days", "Older"). Performance: the list is flat DOM — no virtualization needed for <500 items. |
| Very long prompt text in SessionItem | Truncated to ~60 characters with CSS `text-overflow: ellipsis`. Single line, `overflow-hidden`. |
| Active session deleted externally (CLI) | Next poll shows the session as "failed" or disappears. If the user is viewing that session, the SessionView handles the disconnect gracefully (WS closes, status updates). |

### Model Browser Edge Cases

| Scenario | Behavior |
|----------|----------|
| Models API returns empty | Browser dialog shows "No models available" message. The ModelButton in the composer shows "No models" in muted text. |
| Models API fails | ModelButton shows an error icon. Clicking opens a dialog with "Could not load models — check server connection." |
| Selected model's harness differs from HarnessToggle | HarnessToggle updates to match the model's harness. This is by design — picking a model from a different harness switches the harness. |
| Model catalog changes after initial fetch | No live refresh — catalog is fetched once per app mount. User must reload the page to see new models. This is acceptable because the model catalog changes rarely. |

### Effort Injection Edge Cases

| Scenario | Behavior |
|----------|----------|
| Effort change fails mid-session | EffortSelector reverts to previous value. Toast notification shows "Failed to change effort level." |
| Effort change while spawn is between turns | The injection is queued (Claude) or applied immediately (Codex). The EffortSelector shows the new value optimistically. |
| Harness doesn't support effort mapping | EffortSelector is hidden for unsupported harnesses. If all harnesses eventually support it, this becomes a no-op. Currently: Claude and Codex support effort; OpenCode TBD. |

### Agent Selector Edge Cases

| Scenario | Behavior |
|----------|----------|
| Agents API returns empty (no `.agents/agents/`) | AgentSelector hidden. Sessions created without an agent profile. |
| Selected agent has a different `harness` than current toggle | The agent's `harness` field is informational. It doesn't override the HarnessToggle — the user explicitly chose both. If the combination is invalid, session creation will fail and the error is shown inline. |
| Agent name very long | Truncated in the Select trigger with ellipsis. Full name visible in the dropdown items. |

### Navigation Edge Cases

| Scenario | Behavior |
|----------|----------|
| Browser back/forward between sessions | SessionView unmounts for the old session (WS closes), mounts for the new one (WS opens). State is per-mount, not cached. |
| Browser back from session to landing | SessionView unmounts, EmptyState renders. Session list in sidebar still shows the session. |
| Direct URL paste for unknown session | 404 handling as described above. |
| Page reload on `/s/:sessionId` | SPA fallback serves `index.html`. wouter parses URL. SessionView loads session metadata from API. If spawn is active in current server process, WS reconnects for live streaming. If spawn completed, shows terminal state. |
| Navigate away during streaming | WS closes on unmount (useEffect cleanup). Spawn continues running server-side. Returning to the session reconnects if spawn is still active. |

## Loading States

Each async boundary has a defined loading → ready → error transition:

### Session List (Sidebar)

- **Loading (initial):** Skeleton placeholders — 3 rectangular shimmer blocks stacked vertically in the sidebar.
- **Ready:** Session items render. Groups appear as data populates.
- **Error:** Sidebar body shows muted "Could not load sessions" text. Retries automatically on next poll.
- **Polling (subsequent):** No loading indicator. List updates in-place. New sessions appear at the top with a subtle fade-in.

### Session View

- **Loading:** SessionHeader shows skeleton shimmer for harness/model/status. ThreadView area is empty with a centered spinner.
- **Ready:** Header populates, WS connects, events stream in.
- **Error (404):** "Session not found" centered with return-to-home link.
- **Error (connection):** Header shows "disconnected" dot. Thread area remains visible with whatever was rendered.

### Model Browser

- **Loading:** Dialog opens immediately with skeleton grid — 4 card-shaped shimmer blocks in a 2-column grid.
- **Ready:** Model cards render with data. Currently selected model has ring highlight.
- **Error:** Dialog body shows "Could not load models" with a retry button.

### Session Creation (Composer Submit)

- **Submitting:** Send button shows loading spinner. Controls and textarea are disabled. No navigation until response.
- **Success:** Navigates to `/s/{sessionId}`. Brief transition — no additional loading state needed because SessionView handles its own loading.
- **Error:** Send button re-enables. Error message appears below textarea. All controls remain at their current values.

## Keyboard Navigation

### Composer

- **Tab** cycles through controls: HarnessToggle → ModelButton → EffortSelector → AgentSelector → Textarea → Send.
- **Enter** in textarea sends (existing). **Shift+Enter** for newline (existing).
- **Escape** in textarea blurs focus.
- HarnessToggle and EffortSelector respond to **Arrow Left/Right** (built into Radix ToggleGroup).

### Model Browser

- **Escape** closes the dialog (built into Radix Dialog).
- **Tab** cycles through harness tabs, then model cards.
- **Enter** on a focused model card selects it and closes the dialog.
- Harness tab strip uses **Arrow Up/Down** for navigation.

### Sidebar

- **Tab** from main content wraps to sidebar (natural DOM order: sidebar is first in the flex row).
- Session items are focusable. **Enter** navigates to that session.
- "New Chat" button is the first focusable element in the sidebar.

### Screen Reader Considerations

- SessionItem status dots have `aria-label` describing the status ("Session running", "Session succeeded", etc.).
- HarnessToggle items have `aria-label` with the harness name ("Claude", "Codex", "OpenCode").
- ModelBrowser dialog has `aria-labelledby` pointing to the "Select a Model" title.
- EffortSelector items have `aria-label` with the full label ("Low effort", "Medium effort", etc.).
- Sidebar SessionList has `role="navigation"` and `aria-label="Session history"`.

## Scope Boundaries

### In Scope

- Sidebar with session list, grouped by recency
- Landing page with centered branding + functional composer
- Session view with header, thread, composer
- Composer controls: harness toggle, model browser, effort selector, agent selector
- Client-side routing with wouter
- New backend endpoints: sessions CRUD, models catalog, agents list, effort injection
- SPA static file serving with fallback
- Session persistence across page reloads (via session registry)

### Explicitly Out of Scope

- **Multi-repo support** — The backend session registry supports multi-repo (each session carries a `repo_root`), but the frontend assumes single-repo. No repo selector in the UI. `POST /api/sessions` omits `repo_root`; backend uses server's launch context.
- **File explorer in sidebar** — No file tree, no workspace view.
- **Server lifecycle management** — Covered separately in server-lifecycle.md.
- **Mobile/responsive design** — Desktop-first. Sidebar is always visible at 280px. No collapse/hamburger.
- **Event replay for completed sessions** — Completed sessions show metadata only, not historical thread content. Replay from `output.jsonl` is a future enhancement.
- **Session deletion/archival** — Sessions accumulate. No UI to delete or archive. Acceptable for a local dev tool.
- **Session renaming** — Prompt preview is the only label. No user-editable names.

## Implementation Order

Suggested phasing for implementation:

1. **Routing + layout shell** — Add wouter, restructure App.tsx to sidebar + main pane, create empty Sidebar/EmptyState/SessionView shells. Verify routing works.
2. **Sidebar + session list** — `GET /api/sessions` endpoint, `useSessionList` hook, SessionList/SessionItem components. Verify session navigation.
3. **Session view** — Extract session logic from App.tsx into SessionView. SessionHeader replaces SpawnHeader + StatusBar. Switch useThreadStreaming to session-based addressing.
4. **Composer controls** — HarnessToggle, ModelButton (without browser), EffortSelector, AgentSelector. Wire to session creation. `GET /api/agents` endpoint.
5. **Model browser** — `GET /api/models` endpoint, `useModelCatalog` hook, ModelBrowser dialog with HarnessTabStrip + ModelCard grid.
6. **Effort injection** — `POST /api/sessions/{sid}/effort` endpoint, wire EffortSelector to inject mid-session.
7. **Polish** — Empty state design, transitions, loading states, error states, cleanup SpawnSelector/SpawnHeader.
