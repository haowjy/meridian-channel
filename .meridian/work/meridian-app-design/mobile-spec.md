# Mobile & Responsive Spec

Meridian is a dev tool, but an operator should be able to monitor sessions, glance at dashboards, and send a quick Composer message from a phone. We do not target phone-first authoring; we target monitoring + light intervention.

---

## 1. Breakpoints

| Token | Min width | Target device |
|---|---|---|
| `xs` | 0 px | phone portrait |
| `sm` | 520 px | phone landscape / small tablet portrait |
| `md` | 768 px | tablet portrait |
| `lg` | 1024 px | tablet landscape / small laptop |
| `xl` | 1280 px | laptop |
| `2xl` | 1600 px | large desktop |

Rules:
- **`< md` (under 768 px):** mobile layout — bottom tab bar, full-viewport mode, sheet inspectors, no split panes.
- **`md` to `< lg`:** hybrid — left rail collapses to 40 px icon rail, inspector becomes a sheet, split panes disabled.
- **`≥ lg`:** full desktop layout per `ui-spec.md`.

---

## 2. Mobile shell (< 768 px)

```
┌─────────────────────────────────────────────┐
│ TopNav                                      │
│ ┌─────────────────────────────────────────┐ │
│ │ ≡  work:auth-refactor ▾   ⌘K   ⚙      │ │
│ └─────────────────────────────────────────┘ │
├─────────────────────────────────────────────┤
│                                             │
│              ModeViewport                   │
│              (full width)                   │
│                                             │
│                                             │
│                                             │
│                                             │
│                                             │
│                                             │
├─────────────────────────────────────────────┤
│ BottomBar                                   │
│ ┌───────┬───────┬───────┐                   │
│ │ 📋    │ 💬    │ 📁    │                   │
│ │ Sess. │ Chat  │ Files │                   │
│ └───────┴───────┴───────┘                   │
└─────────────────────────────────────────────┘
```

- **TopNav** (48 px): menu (≡ opens settings drawer), active work-item pill (tap = work item sheet), `⌘K` (search sheet), settings icon. StatusBar content collapses into a single compact pill shown inside TopNav when space allows (e.g., `● 2 · ◐ 1 · ✓`).
- **BottomBar** (56 px, safe-area inset): three-tab mode switcher. Active tab highlighted with accent bar on top. Label under each icon; reduces to icon-only on very small widths (`< 360 px`).
- **ModeViewport**: full width, vertical-scroll, one column only.
- **InspectorPanel** becomes a bottom sheet (swipe up to expand, 60% height by default, drag to full height). Not docked.

---

## 3. Mobile — Sessions mode

- Filter bar collapses into a single horizontally-scrollable chip strip.
- Work item groups render as cards with the same `SessionRow` layout but the row simplifies to two lines:
  ```
  ● p281 · plan · opus-4.7
      running · 2m 14s · auth-refactor
  ```
- Tap a row → Chat mode, that session selected.
- Long-press → context menu (cancel, fork, archive, open log).
- "+ New session" is a floating action button (FAB) bottom-right, 56 px, accent fill. Opens a full-screen `NewSessionDialog`.

---

## 4. Mobile — Chat mode

- **No split panes.** Only one ChatColumn visible at a time.
- SessionList becomes a swipe-in drawer (left edge swipe) or is reachable via a top-left button in ChatHeader.
- ChatHeader shrinks to a single line: `● p281 · plan ▾` (tap for full detail sheet).
- Composer takes full width, fixed to bottom above the BottomBar; grows on focus (up to 40% viewport) then scrolls internally.
- Attachment & mention pickers open as full-screen sheets.
- Inspector: swipe up from the right edge or tap `ⓘ` icon — full-height sheet.

---

## 5. Mobile — Files mode

- Tree and FileView are on separate screens (not side-by-side):
  - Root screen = FileTree (ScopeSwitcher at top).
  - Tap a file → navigate into FileView (full screen).
  - Back button in FileView returns to tree with scroll restored.
- Diff view switches from side-by-side to unified single-column automatically.
- Search field is pinned under the ScopeSwitcher and sticky on scroll.

---

## 6. Tablet / hybrid (768–1023 px)

- Left rail: 40 px icon-only (same affordances as desktop, no labels).
- Split panes in Chat: capped at 2 columns max.
- Inspector: sheet from the right (not docked) to preserve content width.
- StatusBar: visible but condensed; omit port and backend labels, keep counts + git state.

---

## 7. Touch & input targets

- Minimum tap target: 40 × 40 px (WCAG 2.2 AA Enhanced).
- 8 px minimum spacing between adjacent tappable rows.
- Long-press ≥ 500 ms → context menu; light haptic on supported devices (`navigator.vibrate(8)`).
- Swipe gestures:
  - Swipe left on a SessionRow → reveal cancel/archive actions.
  - Swipe down at top of ThreadView → pull-to-refresh the thread (reloads from server).
- Pointer-fine detection (`@media (pointer: fine)`) gates hover-only UI like sparklines — on touch they are tap-to-reveal.

---

## 8. Density & typography on mobile

- Body text bumps from 13 px (desktop) to 14 px for legibility.
- Monospace metadata (spawn ids, elapsed, model) stays 12 px but gets more letter-spacing.
- Line-height 1.5 in content, 1.3 in metadata rows.

---

## 9. Performance budget on mobile

- Initial JS payload ≤ 180 KB gzipped for the shell + active mode route.
- Routes code-split per mode (lazy-loaded on first switch).
- Virtualize every list over 50 rows.
- SSE stream is the only long-lived connection on mobile; pause when the tab is hidden (Page Visibility API) and resume with a since-cursor on visibility.

---

## 10. What mobile deliberately drops (v1)

- Split-pane parallel chats.
- Side-by-side diff.
- The event sparkline per row (replaced by a single colored status dot).
- Drag-drop file attachments (use the system picker).
- Right-hand docked inspector (always a sheet).

These come back at `lg` automatically.
