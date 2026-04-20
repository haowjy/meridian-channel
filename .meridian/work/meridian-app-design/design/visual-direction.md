# Visual Direction

## Design Philosophy

**Dev tool first, approachable second.** The primary users are developers and researchers who live in VS Code, Cursor, Linear, and similar tools. The aesthetic should feel native to that ecosystem: dense information displays, monospace type for identifiers, muted color palettes with semantic highlights, and keyboard-first interactions.

However, non-technical collaborators need to feel comfortable too. This means: clear visual hierarchy, discoverable actions, no jargon-heavy labels, and progressive disclosure of complexity.

## Reference Aesthetic

| Tool | What to borrow |
|------|----------------|
| **Linear** | Work item cards, status pills, grouped lists, clean typography |
| **VS Code** | File explorer patterns, sidebar proportions, activity bar icons |
| **Cursor** | AI session threading, streaming indicators, composer UX |
| **GitHub Issues** | Status badges, metadata density, timeline patterns |

## Color System

Dark mode primary, light mode supported. Colors follow semantic meaning:

### Base Palette

```
Background layers:
  bg-0:  hsl(220, 13%, 8%)    // App background
  bg-1:  hsl(220, 13%, 11%)   // Sidebar, panels
  bg-2:  hsl(220, 13%, 14%)   // Cards, hover states
  bg-3:  hsl(220, 13%, 18%)   // Active states

Text:
  text-primary:   hsl(220, 10%, 90%)   // Primary content
  text-secondary: hsl(220, 8%, 60%)    // Muted content
  text-tertiary:  hsl(220, 6%, 40%)    // Timestamps, metadata

Border:
  border-default: hsl(220, 12%, 18%)
  border-subtle:  hsl(220, 12%, 14%)
```

### Semantic Colors

```
Status:
  running:    hsl(142, 71%, 45%)  // Green pulse
  succeeded:  hsl(142, 50%, 35%)  // Green muted
  failed:     hsl(0, 65%, 50%)    // Red
  cancelled:  hsl(38, 92%, 50%)   // Amber
  idle:       hsl(220, 8%, 50%)   // Gray

Accent:
  accent:        hsl(258, 90%, 66%)  // Purple (Anthropic)
  accent-muted:  hsl(258, 60%, 40%)

Work item types:
  exploration:   hsl(200, 80%, 50%)  // Blue
  implementation: hsl(258, 70%, 55%) // Purple
  review:        hsl(38, 80%, 50%)   // Amber
```

## Typography

### Font Stack

```css
--font-sans: "Inter", "SF Pro Text", -apple-system, sans-serif;
--font-mono: "JetBrains Mono", "SF Mono", "Consolas", monospace;
```

### Type Scale

```
Headers:
  h1: 20px / 600 / -0.01em   // Page titles (rare)
  h2: 16px / 600 / -0.01em   // Section headers
  h3: 14px / 600 / normal    // Card headers

Body:
  body: 14px / 400 / normal         // Primary content
  body-sm: 13px / 400 / normal      // Secondary content
  caption: 12px / 400 / 0.02em      // Metadata, timestamps

Monospace (identifiers, IDs, paths):
  mono: 13px / 450 / normal
  mono-sm: 12px / 450 / normal
```

## Layout System

### Overall Structure

```
┌──────────────────────────────────────────────────────────────────────────┐
│ ┌─────────┬──────────────────────────────────────────────────────────────┤
│ │ Activity│                                                              │
│ │ Bar     │  Main Content Area                                           │
│ │ (48px)  │  (flex-1)                                                    │
│ │         │                                                              │
│ │ [icon]  │                                                              │
│ │ [icon]  │                                                              │
│ │ [icon]  │                                                              │
│ │         │                                                              │
│ │ ─────── │                                                              │
│ │ [⚙]    │                                                              │
│ └─────────┴──────────────────────────────────────────────────────────────┤
└──────────────────────────────────────────────────────────────────────────┘
```

### Spacing Scale

```
space-1:  4px    // Inline elements
space-2:  8px    // Tight grouping
space-3:  12px   // Card padding
space-4:  16px   // Section spacing
space-5:  24px   // Major sections
space-6:  32px   // Page margins
```

## Component Patterns

### Cards

Work item cards are the primary information container:

```
┌─────────────────────────────────────────────────────────────┐
│ ● auth-middleware                                     1h ago │
│                                                              │
│ Implement JWT validation and refresh token flow              │
│                                                              │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐          │
│ │ ○ p42        │ │ ● p43        │ │ ✓ p44        │          │
│ │ orchestrator │ │ coder        │ │ reviewer     │          │
│ └──────────────┘ └──────────────┘ └──────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

Card anatomy:
- Header: status indicator + title + timestamp
- Body: description or prompt preview
- Footer: child sessions or metadata

### Status Indicators

Live pulsing dot for active, solid for terminal:

```
● Running (pulse animation)
○ Idle
✓ Succeeded
✗ Failed
⊘ Cancelled
```

### Badges

Small, muted, high-density:

```
[claude] [opus] [coder]  ← Harness, model, agent
[3 sessions] [2h]        ← Counts, durations
```

### Session List Items

Compact row for sidebar:

```
┌────────────────────────────────────────┐
│ ● p42  orchestrator        2m ago      │
│   Implement auth...                    │
└────────────────────────────────────────┘
```

## Interaction Patterns

### Keyboard-First

| Key | Action |
|-----|--------|
| `⌘K` / `Ctrl+K` | Command palette |
| `⌘N` / `Ctrl+N` | New session |
| `⌘1-9` | Switch to work item |
| `Esc` | Close panels, cancel |
| `Enter` | Submit composer |
| `Shift+Enter` | Newline in composer |

### Progressive Disclosure

1. **Default view**: Work items with session counts
2. **Click work item**: Expand to show sessions
3. **Click session**: Navigate to session view
4. **Advanced toggle**: Reveal harness/model/agent controls

### Hover States

- Cards: subtle bg shift to `bg-2`
- Buttons: slight lift, border highlight
- Links: underline appears

### Loading States

- Skeletons for list items (no spinners)
- Pulse animation for active sessions
- Progress bar in StatusBar during long operations

## File Explorer

Tree pattern borrowed from VS Code:

```
┌─────────────────────────────────────┐
│ EXPLORER                    [···]   │
├─────────────────────────────────────┤
│ ▼ meridian-cli                      │
│   ▼ src                             │
│     ▼ meridian                      │
│       ▶ lib                         │
│       ▶ spawn                       │
│         __init__.py                 │
│   ▶ frontend                        │
│   ▶ tests                           │
│ ▼ another-project                   │
│   ▶ src                             │
└─────────────────────────────────────┘
```

- Chevrons for expand/collapse
- File/folder icons based on type
- Drag to reorder roots (future)
- Context menu for actions

## Responsive Behavior

Desktop-first. Minimum supported width: 1024px.

| Breakpoint | Behavior |
|------------|----------|
| < 1024px | Warning banner, degraded layout |
| 1024-1280px | Compact sidebar (icons only) |
| 1280-1600px | Standard layout |
| > 1600px | Wider main pane, same sidebar |

## Animation

Subtle, functional, never decorative:

```css
--transition-fast: 100ms ease-out;    // Hover states
--transition-default: 150ms ease-out; // Panel transitions
--transition-slow: 250ms ease-out;    // Page transitions

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
```

## Accessibility

- Contrast ratios meet WCAG AA for all text
- Focus rings visible on all interactive elements
- Reduced motion preference respected
- Screen reader landmarks for major sections
- Keyboard navigation for all actions
