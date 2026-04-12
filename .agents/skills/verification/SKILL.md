---
name: verification
description: Use after implementation to get the build green — running tests, type checks, and linters, fixing mechanical breakage, and reporting substantive issues. The "does it compile and pass" baseline, not creative testing. Not the right fit for edge-case coverage (unit-test) or user-flow verification (smoke-test).
---
# Verification

Your job is to get the build green, or clearly report what is blocking it.

## Finding What to Run

Every repo wires verification differently. Identify canonical commands from project docs and CI config:

- README / AGENTS / CLAUDE guidance
- build scripts (`pyproject.toml`, `package.json`, `Makefile`, task runners)
- CI workflows (source of truth for gated checks)

Run the full verification bar used by the project. Do not silently skip configured lanes.

## Core Loop

- Run project verification suite (tests, type checks, lint, format checks used by CI).
- Fix mechanical breakage directly.
- Separate substantive failures from mechanical failures.
- Report final state with actionable blockers.

## If Used as a Phase Tester Lane

When the prompt includes claimed EARS statement IDs:

- verify those IDs explicitly
- report per-ID outcomes with evidence
- use `/ears-parsing` for parse discipline

Use the claimed EARS statement IDs as the acceptance contract for phase-lane verification.

## Mechanical vs Substantive

Mechanical (fix directly):

- import/format/lint noise
- trivial type annotation gaps
- straightforward broken assertions after intentional behavior changes

Substantive (report/escalate):

- logic regressions
- contract mismatches
- design-level type/interface conflicts

## Report Shape

- what ran
- what passed
- what you fixed
- what still fails and why
- next unblock action when not green
