---
name: dev-artifacts
description: Trigger when creating, reading, or deciding where to put artifacts in `$MERIDIAN_WORK_DIR/` — design packages, plans, decision logs, status files, preservation hints.
---
# Dev Artifacts

Durable workflow state lives under `$MERIDIAN_WORK_DIR/`. This skill is the canonical artifact contract — agent bodies defer here for path conventions and ownership so that one place defines the layout and every agent reads from the same source.

The contract matters because spawns end. Anything not on disk does not survive a spawn termination, so artifacts are how design intent reaches planning, how planning intent reaches execution, and how partial progress survives interruption.

## Layout

```text
$MERIDIAN_WORK_DIR/
  requirements.md
  decisions.md
  design/
    spec/                 # behavioral contract (EARS statements with stable IDs)
    architecture/         # technical realization (observational, not prescriptive)
    refactors.md          # rearrangement agenda the planner must account for
    feasibility.md        # probe evidence and assumption verdicts
  plan/
    overview.md           # parallelism posture, rounds, refactor mapping, mermaid fanout, staffing
    phase-N-<slug>.md     # one per phase: scope, EARS claims, exit criteria
    leaf-ownership.md     # one row per spec EARS statement, exclusive phase ownership
    status.md             # phase lifecycle ground truth
    pre-planning-notes.md # planning impl-orch runtime observations before planner spawn
    preservation-hint.md  # redesign cycles only — dev-orch carry-over guidance
```

The spec and architecture trees are hierarchical — sub-trees and overview files inside each, organized by subsystem. The depth and shape match the work-item tier, so small work gets a light tree and large work gets deeper decomposition.

## What Each Artifact Carries

- **`requirements.md`** — captured user intent, constraints, and success criteria. Optional, but worth writing once the problem is non-trivial because it anchors design and gives execution something to verify against.
- **`decisions.md`** — append-only reasoning log for significant judgment calls: design tradeoffs, plan adaptations, overruled reviewers, deferred refactors. Substance over ceremony; resumed runs rehydrate reasoning from these entries, not from the conversation transcript. See `/decision-log` for the writing craft.
- **`design/spec/`** — the behavioral contract. EARS-notation statements with stable IDs are the leaves; spec leaves are what execution verifies against. Hierarchical, with cross-links to the architecture tree.
- **`design/architecture/`** — the technical realization. Observational rather than prescriptive: it describes how the system meets the spec contract, but justified deviations during execution are allowed when logged in `decisions.md`.
- **`design/refactors.md`** — structural rearrangement agenda. The planner must account for every entry, sequencing foundational prep early when present so feature phases can parallelize.
- **`design/feasibility.md`** — probe evidence, validated assumptions, open questions, and fix-or-preserve verdicts. Grounds design decisions in runtime reality. Re-run probes when entries are stale.
- **`plan/overview.md`** — parallelism posture and the cause that drove it, round definitions with per-round justifications, refactor handling for every refactor-agenda entry, a Mermaid fanout that matches the textual rounds, and a staffing section concrete enough that execution impl-orch can spawn workers from it directly.
- **`plan/phase-N-<slug>.md`** — phase-level blueprint: scope and boundaries, touched files and modules, claimed EARS statement IDs, touched refactor IDs, dependencies, tester lane assignment, exit criteria.
- **`plan/leaf-ownership.md`** — one row per spec EARS statement ID with complete and exclusive phase ownership. Tester lane and evidence pointer fields are seeded empty; execution fills them as phases close.
- **`plan/status.md`** — phase lifecycle ground truth. Includes preservation-derived states on redesign cycles so a fresh execution spawn can resume from disk alone.
- **`plan/pre-planning-notes.md`** — planning impl-orch runtime observations captured before the planner spawn: feasibility re-checks, fresh probe results, architecture re-interpretation, module-scoped constraints, leaf-distribution hypothesis, probe gaps.
- **`plan/preservation-hint.md`** — produced by dev-orch between redesign cycles. Tells the next planning impl-orch what carries over and which spec leaves were revised, so preserved phases can be tester-only re-verified.

## Who Writes What

| Artifact | Primary writer | Primary readers |
|---|---|---|
| `requirements.md` | dev-orch | design-orch, impl-orch |
| `design/` (spec, architecture, refactors, feasibility) | design-orch (via architects) | impl-orch, dev-orch |
| `plan/overview.md`, phase blueprints, `leaf-ownership.md`, `status.md` | planner (called by planning impl-orch) | execution impl-orch, dev-orch |
| `plan/pre-planning-notes.md` | planning impl-orch | planner |
| `plan/preservation-hint.md` | dev-orch | next planning impl-orch |
| `decisions.md` | design-orch and impl-orch (append-only) | dev-orch and downstream agents |
| `plan/status.md` updates during execution | execution impl-orch | dev-orch |
| `$MERIDIAN_FS_DIR` | docs-orch (via code-documenters) | all agents |

Artifacts flow forward: design-orch produces the design package; planning impl-orch produces the plan via the planner; execution impl-orch consumes the plan and writes the execution record (status, decisions, leaf-ownership evidence pointers); dev-orch reads everything to review with the user and to route redesign cycles.

## Redesign Brief Lives in the Terminal Report

When an impl-orch escape hatch fires, the redesign brief is a section in the impl-orch terminal report, not a separate file. Each redesign cycle has its own impl-orch spawn with its own report, and meridian persists those reports indefinitely — cross-cycle history is recoverable from spawn history without an extra artifact. The next cycle's preservation hint (which *is* a file) lives in `plan/preservation-hint.md` because it has a different producer (dev-orch) and a different consumer (the next planning impl-orch).

## Rejected Iterations

Replace rejected designs and plans atomically. Approved artifacts live at `design/` and `plan/`; rejected drafts do not get versioned alongside them. Git history preserves prior iterations if anyone needs them. The current state of these directories is always the approved state.

## Documentation Layers

Three distinct documentation surfaces exist, each serving a different audience:

**`$MERIDIAN_FS_DIR` (fs/)** — Agent-facing codebase mirror. Domain-structured compression of the architecture: what exists, how it works, why it's that way. Organized by conceptual domain (named for architectural concepts, not source paths). Agents read this to orient on unfamiliar subsystems without scanning every source file. The `@code-documenter` maintains it; `@dev-orchestrator` triggers `@docs-orchestrator` to coordinate updates after implementation completes.

**`docs/`** — User-facing documentation. CLI reference, getting started guides, configuration docs. Written for humans who use the project, not agents navigating the codebase.

**`$MERIDIAN_WORK_DIR`** — Work-scoped artifacts including research, design, and plans. Research stays here — it is ephemeral context for the current work item. Lasting findings from research get synthesized into the relevant fs/ domain doc when the work completes, not copied verbatim.

fs/ has no `research/` subdirectory. If you are writing research, it belongs in the work item. If the research produced durable knowledge about a subsystem, that knowledge belongs in the fs/ domain doc for that subsystem.

## This Convention Is Swappable

A project or workflow can replace this skill with its own artifact conventions — different directory names, different flow, different files — without touching orchestrator or agent bodies. The convention is a skill, not hardcoded structure.
