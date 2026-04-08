---
name: dev-artifacts
description: Shared artifact convention between orchestrators — what goes where, how artifacts flow between phases, and what each directory means. Use whenever work artifacts, design docs, plans, status tracking, or work structure are being created, referenced, or discussed.
---
# Dev Artifacts

All work artifacts live under `$MERIDIAN_WORK_DIR/`. This convention defines what each directory and file means, who writes it, and how artifacts flow between orchestrators. Every orchestrator shares this understanding — it's how design intent survives the handoff to implementation.

## The Directories

**`design/`** — The target system state. Model how the system *should* look after implementation, including existing parts the work interacts with. Design docs follow the structure and writing conventions in `/tech-docs` — one concept per doc, linked, hierarchically organized. Describes what the system should become, not how it evolved to get there.

**`plan/`** — The delta from current codebase to designed state. Each phase file is scoped, ordered, and verifiable against design/. Plan says *what changes*; design says *what it should look like*.

**`decisions.md`** — Execution-time pivots, review triage, overruled @reviewers — with reasoning. Written as implementation discovers reality that the design didn't anticipate. (See the decision-log skill for the craft of writing decisions.)

**`plan/status.md`** — Ground truth for phase progress. The @impl-orchestrator maintains this as phases start, complete, or hit blockers.

**`requirements.md`** (optional) — Captured user intent, constraints, and success criteria. Write this when the problem needs anchoring before design begins. @design-orchestrator optimizes toward it; @impl-orchestrator verifies against it.

## Who Writes What

| Artifact | Written by | Read by |
|---|---|---|
| requirements.md | @dev-orchestrator | @design-orchestrator, @impl-orchestrator |
| design/ | @design-orchestrator (via @architects) | @impl-orchestrator, @dev-orchestrator |
| plan/ | @design-orchestrator (via @planners) | @impl-orchestrator, @dev-orchestrator |
| plan/status.md | @impl-orchestrator | @dev-orchestrator |
| decisions.md | @impl-orchestrator | @dev-orchestrator |
| $MERIDIAN_FS_DIR | @docs-orchestrator (via @code-documenters) | all agents |

Artifacts flow forward: @design-orchestrator writes the specification (design/ + plan/), @impl-orchestrator reads it and writes the execution record (plan/status.md + decisions.md), @dev-orchestrator reads everything to review with the user.

## Rejected Iterations

Replace rejected designs atomically. Approved artifacts live at `design/` and `plan/` — not versioned alongside rejected drafts. Git history preserves prior iterations if anyone needs them. The current state of these directories is always the approved state.

## Documentation Layers

Three distinct documentation surfaces exist, each serving a different audience:

**`$MERIDIAN_FS_DIR` (fs/)** — Agent-facing codebase mirror. Domain-structured compression of the architecture: what exists, how it works, why it's that way. Organized by conceptual domain (named for architectural concepts, not source paths). Agents read this to orient on unfamiliar subsystems without scanning every source file. The @code-documenter maintains it; the @dev-orchestrator triggers the @docs-orchestrator to coordinate updates after implementation completes.

**`docs/`** — User-facing documentation. CLI reference, getting started guides, configuration docs. Written for humans who use the project, not agents navigating the codebase.

**`$MERIDIAN_WORK_DIR`** — Work-scoped artifacts including research, design, and plans. Research stays here — it's ephemeral context for the current work item. Lasting findings from research get synthesized into the relevant fs/ domain doc when the work completes, not copied verbatim.

fs/ has no `research/` subdirectory. If you're writing research, it belongs in the work item. If the research produced durable knowledge about a subsystem, that knowledge belongs in the fs/ domain doc for that subsystem.

## This Convention Is Swappable

A project or workflow can replace this skill with its own artifact conventions — different directory names, different flow, different files — without touching orchestrator or agent bodies. The convention is a skill, not hardcoded structure.
