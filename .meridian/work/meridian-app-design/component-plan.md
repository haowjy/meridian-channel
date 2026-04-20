# Component Plan — Reuse vs Build

**Target codebase:** `frontend/src/` (React + TypeScript + Vite, existing).

Rule of thumb: **the chat surface is solid — reuse everything under `features/threads/`**. The dashboard and files modes are net-new. The shell (rail, status bar, top bar) is new but shallow.

---

## 1. Reuse (do not rewrite)

| Component | Path | Used in |
|---|---|---|
| `ThreadView` | `frontend/src/features/threads/components/ThreadView.tsx` | Chat mode (every column) |
| `Composer` | `frontend/src/features/threads/composer/Composer.tsx` | Chat mode (every column) |
| `ActivityItem` | under `frontend/src/features/threads/**` | Chat mode, Sessions inspector |
| Message / ToolCall / Block renderers | under `frontend/src/features/threads/**` | Chat + inspectors |
| Existing thread hooks (stream, send, cancel) | under `frontend/src/features/threads/**` | Chat mode |

**Actions:**
- Wrap `ThreadView` in a thin `ChatColumn` to add the new header + split-pane container; do not modify `ThreadView` itself.
- Extend `Composer` only to support `@file` / `@session` mentions — ideally via a pluggable mention provider prop, not a fork.

---

## 2. New — shell layer

| Component | Location (suggested) | Notes |
|---|---|---|
| `AppShell` | `frontend/src/shell/AppShell.tsx` | Three-slot grid: rail / body / status bar |
| `ModeRail` | `frontend/src/shell/ModeRail.tsx` | 48 px, icon-only, active accent bar, keyboard `⌘1/2/3` |
| `TopBar` | `frontend/src/shell/TopBar.tsx` | Workspace, branch, active work-item pill, `⌘K`, settings |
| `StatusBar` | `frontend/src/shell/StatusBar.tsx` | Spawn counts, git state, port, backend health |
| `InspectorPanel` | `frontend/src/shell/InspectorPanel.tsx` | Right-hand 320 px collapsible drawer, mode-agnostic wrapper |
| `CommandPalette` | `frontend/src/shell/CommandPalette.tsx` | `⌘K`, fuzzy list driven by providers per mode |
| `ThemeProvider` | `frontend/src/shell/ThemeProvider.tsx` | Token wiring, light/dark/auto |

---

## 3. New — Sessions mode

| Component | Location | Notes |
|---|---|---|
| `SessionsPage` | `frontend/src/features/sessions/SessionsPage.tsx` | Page-level orchestration |
| `SessionsFilterBar` | `…/sessions/SessionsFilterBar.tsx` | Status chips + selects; persists to URL |
| `WorkItemGroup` | `…/sessions/WorkItemGroup.tsx` | Collapsible section; header with sync badge |
| `SessionRow` | `…/sessions/SessionRow.tsx` | Fixed-grid row; used in Sessions mode and (compact form) in Chat's SessionList |
| `SessionRowCompact` | `…/sessions/SessionRowCompact.tsx` | Narrow single-line variant for sidebar |
| `NewSessionDialog` | `…/sessions/NewSessionDialog.tsx` | Command-palette-styled modal |
| `SessionInspector` | `…/sessions/SessionInspector.tsx` | params, event tail, artifacts |
| `SpawnActivitySparkline` | `…/sessions/SpawnActivitySparkline.tsx` | Tiny SVG, 60 s window |

---

## 4. New — Chat mode (thin shell on top of existing)

| Component | Location | Notes |
|---|---|---|
| `ChatPage` | `frontend/src/features/chat/ChatPage.tsx` | SessionList + ChatColumns layout |
| `SessionList` | `…/chat/SessionList.tsx` | Uses `SessionRowCompact`; search + grouping |
| `ChatColumn` | `…/chat/ChatColumn.tsx` | Header + `ThreadView` + `Composer`; split-pane member |
| `ChatHeader` | `…/chat/ChatHeader.tsx` | Session metadata, actions |
| `SplitPane` | `frontend/src/shared/SplitPane.tsx` | Resizable, reorderable horizontal split (or pull in an existing lib) |
| `ChatInspector` | `…/chat/ChatInspector.tsx` | Per-message raw events, tool-call detail, token usage |

---

## 5. New — Files mode

| Component | Location | Notes |
|---|---|---|
| `FilesPage` | `frontend/src/features/files/FilesPage.tsx` | Tree + FileView layout |
| `ScopeSwitcher` | `…/files/ScopeSwitcher.tsx` | Work / Spawn / Repo |
| `FileTree` | `…/files/FileTree.tsx` | Virtualized; needs `@tanstack/react-virtual` or similar |
| `FileTreeNode` | `…/files/FileTreeNode.tsx` | Row primitive |
| `Breadcrumb` | `frontend/src/shared/Breadcrumb.tsx` | Reusable |
| `FileView` | `…/files/FileView.tsx` | Tabs: rendered / raw / diff |
| `MarkdownRenderer` | `frontend/src/shared/MarkdownRenderer.tsx` | If not already present |
| `DiffView` | `frontend/src/shared/DiffView.tsx` | Wrap an existing diff renderer (e.g. `diff2html` or `@git-diff-view/react`) |
| `FileInspector` | `…/files/FileInspector.tsx` | Meta, git log, referenced-by |

---

## 6. New — shared primitives

| Component | Location | Notes |
|---|---|---|
| `StatusDot` | `frontend/src/shared/StatusDot.tsx` | Shape+color; drives the pulse animation |
| `WorkItemPill` | `frontend/src/shared/WorkItemPill.tsx` | Global; click switches active work item |
| `GitSyncBadge` | `frontend/src/shared/GitSyncBadge.tsx` | Reusable in Sessions + Files + TopBar |
| `KeymapHint` | `frontend/src/shared/KeymapHint.tsx` | Faint inline chip |
| `IconButton`, `Tooltip`, `Menu`, `Dialog`, `Popover` | `frontend/src/shared/ui/*` | Use Radix UI primitives (unstyled) + local tokens |
| `Toast` | `frontend/src/shared/Toast.tsx` | For sync + spawn-failed notifications |
| `EmptyState` | `frontend/src/shared/EmptyState.tsx` | Reused in all three modes |

---

## 7. State & data layer

- **Server state:** TanStack Query (`@tanstack/react-query`) for all REST/SSE-backed data; use the existing thread WS hooks unchanged.
- **SSE multiplexer:** single `useMeridianStream()` hook driving invalidations on React Query caches for `spawns`, `work`, `stats`.
- **Client state:** Zustand store (small) for:
  - active mode, active work item, active session(s), chat layout, inspector open/closed, theme.
- **URL state:** mode + selected session + selected file are reflected in the URL (`react-router` or `@tanstack/router`).

---

## 8. Libraries to add (if not already present)

- `@tanstack/react-query` — server state
- `@tanstack/react-virtual` — virtualized trees & lists
- `radix-ui` (or `@radix-ui/react-*`) — a11y-correct primitives
- `motion` (formerly Framer Motion) — if we want spring-based transitions; otherwise pure CSS
- `cmdk` — command palette engine
- `@git-diff-view/react` or `diff2html` — diff rendering
- `shiki` or `prism-react-renderer` — syntax highlight in FileView + ThreadView code blocks (verify what ThreadView already uses)

Do not add UI kits like Material / Chakra / Ant — they fight the dev-tool aesthetic.

---

## 9. Touch list — what the coder must actually change

Must-touch existing files:
- `frontend/src/App.tsx` → replace top-level with `AppShell` + router.
- `frontend/src/features/threads/composer/Composer.tsx` → add mention-provider prop (tiny, additive).

Must not touch (reuse as-is):
- Everything inside `frontend/src/features/threads/` apart from the additive Composer prop.

Everything else is greenfield under `shell/`, `shared/`, `features/sessions/`, `features/chat/`, `features/files/`.
