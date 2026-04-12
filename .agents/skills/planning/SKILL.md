---
name: planning
description: Use after a design package exists and before coders are spawned — decomposing a design into executable phases, writing phase blueprints, mapping dependencies, sequencing refactors, and figuring out parallelism posture. Not the right fit when the design itself is unresolved (escalate back to design instead).
---

# Plan Implementation

Design describes target state. Plan describes execution delta.

The plan is a delta, not a restatement of the full system. The point is to translate design intent into phase-by-phase executable work with explicit ownership and verification.

Planner output must be executable by impl-orch without hidden assumptions.

## Inputs You Must Consume

- `design/spec/` tree
- `design/architecture/` tree
- `design/refactors.md`
- `design/feasibility.md`
- `plan/pre-planning-notes.md`
- `plan/preservation-hint.md` (when present)
- `requirements.md`
- relevant decision/audit artifacts in the work directory

## Thoroughness Is Mandatory

Shallow planning causes shallow implementation, and shallow implementation ships bugs that design and probes already warned about.

Before declaring plan-ready, walk every decision entry, edge case, and audit finding into a concrete phase contract. No input gets to evaporate between your read and the coder's blueprint.

Thoroughness checks:

- Every numbered decision points to an exact phase and artifact owner.
- Every spec edge case points to exact verification evidence ownership.
- Every audit or probe gap points to the phase that closes it.

If any of those checks produce "none," planning is incomplete.

Thorough planning is expensive. Do it anyway. Re-implementing on a thin plan costs more.

## Planning Priorities

- Parallelism-first decomposition with explicit round constraints.
- Structural refactors early when they unlock parallel feature work.
- Complete and exclusive ownership of EARS statements.
- Clear tester lanes and evidence expectations per phase.

## Phase Decomposition

Break work into phases that a single coder can complete in one focused session.

A good phase is:

- **Independently testable** (most important): completion can be verified without waiting on later phases.
- **Bounded to specific files/modules**: ownership is clear and cross-phase collision risk stays low.
- **Right-sized**: substantial enough to matter, small enough to complete and review cleanly.

Keep blueprints self-contained. Include only context that changes implementation decisions.

## Required Files

Write exactly:

1. `plan/overview.md`
2. `plan/phase-N-<slug>.md` files
3. `plan/leaf-ownership.md`
4. `plan/status.md`

## `plan/overview.md` Contract

Include:

- `Parallelism Posture` and `Cause`
- round list
- per-round justifications tied to concrete constraints
- refactor-handling table covering every `R0N`
- Mermaid fanout matching the round list
- explicit staffing contract for per-phase teams and final review loop

## Staffing Is Mandatory Output

Every plan must include staffing concrete enough for impl-orch to execute directly.

Staffing contract must include:

1. **Per-phase teams**: coder model, tester lanes (`@verifier`, `@smoke-tester`, `@unit-tester`, `@browser-tester` as applicable), and intermediate-phase escalation reviewer policy.
2. **Final review loop**: reviewer model mix, focus lanes, and structural review assignment.
3. **Escalation policy**: when tester findings require scoped reviewer intervention instead of direct fix/retest.

A plan without staffing drives execution toward coder-only behavior with weak review loops.

## Phase Blueprint Contract

Each phase file includes:

- scope and boundaries
- touched files/modules
- claimed EARS statement IDs
- touched refactor IDs
- dependencies
- tester lanes
- exit criteria

## `plan/leaf-ownership.md` Contract

- One row per EARS statement ID (`S<subsystem>.<section>.<letter><number>`)
- Complete + exclusive ownership
- Status, tester lane, evidence pointer
- Revised annotation propagation on redesign cycles (`revised: <reason>`)

## Non-Negotiable Rules

- Sequence the refactor agenda exactly as declared in `design/refactors.md`, including foundational prep entries when present.
- If runtime context is missing, emit a probe-request with specific questions.
- If design preserves structural coupling that blocks decomposition, emit structural-blocking.

## Terminal Shapes

- `plan-ready`
- `probe-request`
- `structural-blocking`
