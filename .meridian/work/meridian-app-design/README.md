# Meridian App Design

This directory is the implementation index for Meridian App UI and API design work.

## Authoritative Specs (implement from these)

These docs are the source of truth for build decisions and acceptance checks:

| Document | Scope |
|---|---|
| `ui-spec.md` | UI layout, modes, components, interactions, keyboard/a11y behavior |
| `backend-gaps.md` | Required backend API surface for the frontend redesign |
| `component-plan.md` | Component ownership: what to reuse vs what to build |
| `mobile-spec.md` | Responsive and mobile behavior by breakpoint |

## Requirements & Features

| Document | Scope |
|---|---|
| `requirements.md` | Functional and non-functional requirements |
| `features.md` | User-facing feature set and priorities (P0/P1/P2) |

## Design Decisions

| Document | Scope |
|---|---|
| `decisions.md` | Decision log with rationale and rejected alternatives |

## Supporting Design Docs (`design/`)

These are supporting references. Status indicates whether each doc remains canonical or has been superseded by top-level specs.

| Document | Status | Notes |
|---|---|---|
| `design/visual-direction.md` | Canonical | Design tokens and visual system details referenced by `ui-spec.md` |
| `design/HARNESS-CONTROL-MATRIX.md` | Canonical | Per-harness control behavior and capability constraints |
| `design/session-registry.md` | Canonical | Session identity and storage model details |
| `design/server-abstraction.md` | Canonical | Local-first vs cloud abstraction boundary |
| `design/server-lifecycle.md` | Canonical | Single-server lifecycle and lockfile behavior |
| `design/project-key.md` | Canonical | Project identity model (`project_key`) |
| `design/overview.md` | Superseded | Replaced by `ui-spec.md`, `backend-gaps.md`, and `component-plan.md` |
| `design/dashboard-layout.md` | Superseded | Replaced by Sessions-mode layout in `ui-spec.md` |
| `design/sidebar.md` | Superseded | Replaced by mode shell + list definitions in `ui-spec.md` and `component-plan.md` |
| `design/session-cards.md` | Superseded | Replaced by `SessionRow` and related component definitions in `component-plan.md` |
| `design/file-explorer.md` | Superseded | Replaced by Files-mode behavior in `ui-spec.md` and API needs in `backend-gaps.md` |
| `design/frontend-routing.md` | Superseded | Replaced by current mode-based routing in `ui-spec.md` |

## Superseded Source Work Items

- `app-session-architecture/` (absorbed)
- `harness-policy-ui-design/` (absorbed)
