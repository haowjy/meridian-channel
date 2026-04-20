# Meridian App — UI Specification

**Status:** final spec for @frontend-coder
**Port:** 7676 (气流 / "airflow")
**Aesthetic:** dev-tool (VS Code / Cursor / Linear family) — information-dense, monospace-forward, restrained color

---

## 1. Global Shell

The app is a single-page, three-mode workspace. Mode is a first-class piece of navigation state (`/sessions`, `/chat`, `/files`) — not a tab inside a page. Each mode owns the full viewport minus the persistent rail.

### Desktop shell (≥ 1024 px)

```
┌────┬─────────────────────────────────────────────────────────────────────┐
│    │ ┌─ TopBar ──────────────────────────────────────────────────────┐  │
│ M  │ │ workspace ▾   branch●   work:auth-refactor   ⌘K   ⚙  jh       │  │
│ 📋 │ └────────────────────────────────────────────────────────────────┘  │
│ 💬 │                                                                     │
│ 📁 │                     ModeViewport                                    │
│    │                     (Sessions | Chat | Files)                      │
│ ─  │                                                                     │
│ +  │                                                                     │
│    │                                                                     │
│ ⚙  │ ┌─ StatusBar ─────────────────────────────────────────────────────┐│
│    │ │ ● running 2   ◐ queued 1   ✓ 14   ✗ 0   ▲ git:ahead-1   7676  ││
│    │ └─────────────────────────────────────────────────────────────────┘│
└────┴─────────────────────────────────────────────────────────────────────┘
  │    │
  │    └─ right edge: optional InspectorPanel (mode-specific, collapsible)
  └─ ModeRail (48 px): Sessions / Chat / Files, + New, settings
```

- **ModeRail** is always visible; 48 px wide; icons only; active mode has a 2 px accent bar on the left edge and the icon shifts to full-opacity.
- **TopBar** (44 px): workspace switcher, git/branch indicator, active work-item pill, global command palette (⌘K), settings, avatar. Content inside is mode-agnostic.
- **StatusBar** (24 px): Linear/VS Code–style footer. Spawn counts, git sync state, backend health, port. Click a counter to filter the active mode.
- **InspectorPanel** is a right-hand 320 px drawer that each mode may open for focused detail (session metadata, tool-call payload, file diff). Toggled by `I` or an explicit button in that mode's header.

### Color & type rails

See `design/visual-direction.md` for the full token set. Highlights:
- Body: mono UI font (JetBrains Mono / Berkeley Mono / Commit Mono) at 13 px.
- Display: a sharp neo-grotesque (e.g. Söhne, Basis Grotesk) for headings and empty states.
- Dominant neutral surface with a single, high-chroma accent (pick: electric cyan #4cffd7 **or** signal amber #ffb347 — not both). Accent is used for active mode, running-status pulse, and primary actions only.
- Light & dark themes share identical layout and spacing; only token values flip.

---

## 2. Mode: Sessions (📋) — the dashboard

**Purpose:** answer "what's running, what's queued, what just finished, where's the one I need to look at?"

Sessions = spawns. Work items are the organizing spine. A session is always attached to a work item (implicit "scratch" work item when user hasn't picked one).

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Sessions                                           [+ New session]  [I] │
├─────────────────────────────────────────────────────────────────────────┤
│ ┌── Filters ───────────────────────────────────────────────────────┐   │
│ │ all ▪ running ▪ queued ▪ done ▪ failed      work: ▾    agent: ▾ │   │
│ └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│ ▾ auth-refactor                         6 sessions · git:ahead 1 · ↻   │
│   ● p281  plan                claude-opus-4.7  running  2m    42%      │
│   ● p280  frontend-coder      claude-sonnet    running  4m    —        │
│   ◐ p283  tester              claude-haiku     queued   —     —        │
│   ✓ p274  frontend-designer   claude-opus-4.7  done   12m                │
│   ✗ p268  plan                claude-opus-4.7  failed  8m                │
│                                                                         │
│ ▾ context-backend                       3 sessions · git:synced          │
│   ✓ p272  plan                claude-opus-4.7  done   22m                │
│   ...                                                                   │
│                                                                         │
│ ▸ (unattached)                          2 sessions                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### Components

- **WorkItemGroup** — collapsible section header per work item, showing:
  - name, session count, **git sync badge** (`synced` / `ahead N` / `behind N` / `diverged` / `dirty`), last activity, a small `↻` sync button when behind/dirty.
  - source: `context-backend` provides git sync state (see `backend-gaps.md`).
- **SessionRow** — single line, fixed grid:
  ```
  [status-dot] [spawn_id] [agent] [model] [state-text] [elapsed] [progress/tokens]
  ```
  - left-click: open in Chat mode (switches mode, selects this session).
  - right-click / `…` menu: cancel, fork, open session log, archive, re-run.
  - hover: inline sparkline of activity events over last 60 s.
- **Filter bar** — chips for status, popover selects for work-item and agent. Filters persist in URL.
- **"+ New session" dialog** — a compact command-palette-style modal:
  - agent (searchable), model (auto-routed by agent default, overridable), work item (picker + "create new"), initial prompt (multiline), reference files (drag-drop or `@`-mention).
  - live preview of the resolved `meridian spawn` CLI invocation at the bottom (copyable).
- **Inspector (I)** — selected session detail: params.json view, output event stream (tail), artifacts list, finalization state.

### Empty state
Large display-font quote ("Nothing running. 7676 is quiet."), a subtle ASCII windsock motif, and a single CTA: **New session**.

---

## 3. Mode: Chat (💬) — the conversation surface

**Purpose:** talk to one session (or many, side-by-side) in real time. This is where the existing `ThreadView` + `Composer` live.

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Chat                                                            [I]     │
├──────────────┬──────────────────────────────────────────────────────────┤
│ SessionList  │ ┌─ ThreadHeader ────────────────────────────────────┐   │
│ (240 px)     │ │ p281  plan · claude-opus-4.7 · work:auth-refactor │   │
│              │ │ ● running · 2m 14s · ↗ fork · ⏸ cancel            │   │
│ [+ New]      │ └────────────────────────────────────────────────────┘   │
│              │                                                          │
│ ▼ auth-refac │   [ThreadView — existing component, unchanged]           │
│  ● p281 ...  │                                                          │
│  ● p280 ...  │   ActivityItem • ActivityItem • ToolCall • Message       │
│  ✓ p274 ...  │                                                          │
│              │                                                          │
│ ▼ context-bk │                                                          │
│  ✓ p272 ...  │                                                          │
│              │ ┌─ Composer (existing) ─────────────────────────────┐   │
│              │ │ > ...                                    [attach] │   │
│              │ └────────────────────────────────────────────────────┘   │
└──────────────┴──────────────────────────────────────────────────────────┘
```

### Multi-session layout (parallel sessions)

User can split the thread pane into 2–4 columns, each bound to a different session. Columns share the SessionList; the Composer of each column is independent.

```
┌──────────────┬─────────────────────┬─────────────────────┬──────────────┐
│ SessionList  │ p281 · plan         │ p280 · frontend     │ p274 · tester│
│              │ [ThreadView]        │ [ThreadView]        │ [ThreadView] │
│              │ [Composer]          │ [Composer]          │ [Composer]   │
└──────────────┴─────────────────────┴─────────────────────┴──────────────┘
```

- Split via header action `⎘ Split right` or `⌘\`.
- Columns are drag-reorderable; close via `⌘W`.
- Layout is persisted per work item.

### Components

- **SessionList** — reuses the same row primitive as the Sessions mode but in a narrower, single-line truncated form. Active session has the accent bar.
- **ThreadHeader** — session id, agent, model, work item pill (click → jump to work item), status, quick actions (fork, cancel, copy chat id, open logs).
- **ThreadView** — *existing, reuse.* Lives under `frontend/src/features/threads/components/ThreadView.tsx`.
- **Composer** — *existing, reuse.* Lives under `frontend/src/features/threads/composer/Composer.tsx`. Add: `@file` mention autocomplete backed by the Files mode tree (new), `@session` mention (cross-reference another spawn).
- **Inspector (I)** — per-turn detail: raw StreamEvents, tool-call inputs/outputs, token accounting, cost. Shift-click any ActivityItem pins it here.

---

## 4. Mode: Files (📁) — the project file explorer

**Purpose:** browse files under the current project root (the directory where `meridian app` started) and diff them. Read-first; edits are out-of-scope for v1 (open in editor is fine).

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Files                                                           [I]     │
├──────────────┬──────────────────────────────────────────────────────────┤
│ Tree (280px) │ ┌─ Breadcrumb ─────────────────────────────────────────┐│
│              │ │ meridian-cli › .meridian › work › ... › overview.md ││
│              │ └──────────────────────────────────────────────────────┘│
│              │                                                          │
│ Project root │   ┌─ FileView ─────────────────────────────────────┐    │
│   /repo      │   │  markdown rendered   |   raw   |   diff        │    │
│              │   │                                                 │    │
│ ▾ design/    │   │  # Meridian App — Overview                      │    │
│   overview.md│   │                                                 │    │
│   sidebar.md │   │  ...                                            │    │
│ ▸ fanout/    │   │                                                 │    │
│ ▸ reports/   │   └─────────────────────────────────────────────────┘    │
│              │                                                          │
│              │   status: git:modified  ·  2.3 KB  ·  last sync 34s      │
└──────────────┴──────────────────────────────────────────────────────────┘
```

### Components

- **ProjectRootHeader** — top of tree; shows the bound project root and active branch/sync status.
- **FileTree** — virtualized tree rooted at the bound project directory, with file icons per extension and optional git status badges.
- **Breadcrumb** — clickable path segments; terminal segment is the filename with a copy button.
- **FileView** — tabs for `rendered` (md/html/ipynb/image/json), `raw`, `diff` (against git HEAD or another ref). For large files, streams via the backend.
- **Inspector (I)** — file metadata: size, mtime, git log (short), contributors, and "referenced by" (which sessions mention this file).

---

## 5. Global primitives

- **StatusDot** — semantic color; shapes that encode state without relying on color alone: `●` running (pulsing), `◐` queued, `✓` done, `✗` failed, `◯` cancelled, `…` finalizing.
- **WorkItemPill** — compact chip with name + sync dot. Clickable anywhere it appears to switch the global active work item.
- **GitSyncBadge** — text + dot: `synced`, `ahead·1`, `behind·2`, `diverged`, `dirty`.
- **KeymapHint** — faint inline `⌘K` / `⌘\\` chips next to affordances.
- **CommandPalette (⌘K)** — global fuzzy: switch work item, open session, open file, run agent, change theme, toggle inspector. Single entry point.

---

## 6. Interaction & motion

- Mode switching: 120 ms cross-fade of the ModeViewport, ModeRail accent bar slides with a spring (stiffness 400, damping 32).
- Session row status change: pulse the status-dot for 800 ms on transition, never on initial render (CSS `@starting-style` + keyframes).
- New session appears: inserted with a 1-row expand from 0 → full height, 180 ms ease-out.
- Finalizing → terminal: subtle progress bar fills the row's left edge once, then the badge flips.
- Motion respects `prefers-reduced-motion`.

---

## 7. Keyboard map (desktop)

| Key | Action |
|---|---|
| `⌘K` | Command palette |
| `⌘1 / ⌘2 / ⌘3` | Switch to Sessions / Chat / Files |
| `⌘N` | New session (works from any mode) |
| `⌘\\` | Split current chat right |
| `⌘W` | Close current chat column |
| `I` | Toggle mode inspector |
| `⌘,` | Settings |
| `J / K` | Next / prev in any list |
| `/` | Focus filter/search in active mode |

Everything that is clickable must be reachable via keyboard; every keyboard action must have a visible affordance somewhere.

---

## 8. Accessibility

- Full keyboard loop with visible `:focus-visible` rings (2 px accent, 2 px surface offset).
- Status conveyed via shape + text, not just color.
- All live regions (status bar counters, streaming chat) announce politely (`aria-live="polite"`) — except errors (`assertive`).
- Target 4.5:1 contrast minimum for all non-decorative text in both themes.

---

## 9. What this spec deliberately leaves open

- Exact token values (colors, spacing scale) — covered by `design/visual-direction.md`.
- The drag-drop behavior between work items (reassigning a session) — v2.
- In-browser file editing — v2; v1 offers "reveal in editor" via a local URI scheme.
