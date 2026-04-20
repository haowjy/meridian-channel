# Meridian App Design

Consolidated design for the Meridian web UI — a dev-tool-first interface for AI-assisted work.

## Design Philosophy

- **Work items are first-class** — sessions grouped by work context, not by repo or recency
- **Dev tool aesthetic** — VS Code/Cursor/Linear visual language
- **Simple by default** — effort toggle, advanced settings hidden
- **Local-first, cloud-ready** — abstractions in place for future cloud backend

## Design Documents

| Document | Purpose |
|----------|---------|
| `design/overview.md` | Master design document — start here |
| `design/visual-direction.md` | Color, typography, spacing, interaction patterns |
| `design/dashboard-layout.md` | Work-item-centric dashboard design |
| `design/sidebar.md` | Sidebar with work-grouped sessions |
| `design/session-cards.md` | Session and work item card components |
| `design/file-explorer.md` | Multi-root file explorer |
| `design/frontend-routing.md` | Routes and component structure |
| `design/session-registry.md` | Session storage and API |
| `design/server-abstraction.md` | Future cloud swappability |
| `design/HARNESS-CONTROL-MATRIX.md` | Per-harness control capabilities |
| `design/server-lifecycle.md` | Server start/stop, lockfile |
| `design/project-key.md` | Project identity, multi-repo support |

## Implementation Phases

1. **MVP**: Dashboard, session view, sidebar, file explorer, basic controls
2. **Mid-session controls**: Model switching, compact, skills, spawn tree
3. **Polish**: Event replay, remote access, cloud abstraction

## Superseded

These work items are superseded by this consolidated design:
- `app-session-architecture/` (absorbed)
- `harness-policy-ui-design/` (absorbed)
