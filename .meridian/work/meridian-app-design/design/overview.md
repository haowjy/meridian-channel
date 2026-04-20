# Meridian App — High-Level Overview

**Version**: 2026-04-19 (reconciled to canonical UI/backend/component specs)

## Purpose

This document is the high-level architecture summary for the Meridian app.
It is not the source of truth for UI behavior, component structure, or endpoint contracts.

## Canonical Detailed Specs

- UI behavior, navigation modes, shell, and interaction details: `ui-spec.md`
- Backend endpoint surface and API contract gaps: `backend-gaps.md`
- Frontend reuse/build decisions and component ownership: `component-plan.md`

## Superseded Sections

The following sections were intentionally removed from this overview because they are now canonical elsewhere:

- Detailed routes table -> superseded by mode model in `ui-spec.md`
- Component hierarchy tree -> superseded by `component-plan.md`
- API endpoint tables -> superseded by `backend-gaps.md`

## Vision

A dev-tool-first web UI for AI-assisted work. Work items are the organizing principle. Simple by default, powerful when needed. `meridian app` serves exactly one project root, like Jupyter Notebook serves one working directory.

## Architecture

### Server Model

One server per project root (Jupyter-style). Starting `meridian app` from a repo binds that server to the current working directory and serves it at `http://localhost:7676`.

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser (localhost:7676)                                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Sessions (/sessions) │ Chat (/chat) │ Files (/files)   │   │
│  └──────────────────────────────────────────────────────────┘   │
│         │ REST / WS / SSE                                       │
└─────────┼────────────────────────────────────────────────────────┘
          │
┌─────────┼────────────────────────────────────────────────────────┐
│  FastAPI Server (localhost:7676)                                 │
│  ├── SessionRegistry (.meridian/app/sessions.jsonl)              │
│  ├── SpawnManager (harness connections)                          │
│  ├── FileExplorer (project-root filesystem access)               │
│  └── WorkItemAPI (queries meridian work layer in this project)   │
└──────────────────────────────────────────────────────────────────┘
          │
┌─────────┴────────────────────────────────────────────────────────┐
│  Harness Runtimes                                                │
│  Claude Code (subprocess) | Codex (JSON-RPC) | OpenCode (HTTP)   │
└──────────────────────────────────────────────────────────────────┘
```

### Core Domain Concepts

- **Session**: metadata alias mapping `session_id -> (spawn_id, repo_root, work_id)`
- **Work Item**: first-class grouping of related sessions
- **Project Root**: the single filesystem root bound at server start
- **Spawn**: Meridian run identity, the underlying harness process

## Composer

Composer behavior is specified in `ui-spec.md`:

- Sessions mode: new-session flow (dialog/palette style) with prompt, agent/model resolution, and work attachment
- Chat mode: active-session composer built on existing thread surface, with mention support and per-session send flow

This overview intentionally avoids duplicating control-level composer requirements.

## Related Documents

- `ui-spec.md`
- `backend-gaps.md`
- `component-plan.md`
- `visual-direction.md`
- `HARNESS-CONTROL-MATRIX.md`
