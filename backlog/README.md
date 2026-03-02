# Backlog

Central backlog for cross-cutting work not tied to a single implementation plan.

## Priority Index

| ID | Item | File | Priority |
|----|------|------|----------|
| BUG-1 | Orphaned spawns stay "running" forever | `bugs.md` | High |
| BUG-2 | Report not overwritten cleanly between runs | `bugs.md` | High |
| BUG-3 | Token usage always reports 0/0 | `bugs.md` | Medium |
| BUG-4 | Thin auto-extracted reports with pseudo-paths | `bugs.md` | Medium |
| BUG-5 | Empty artifacts on spawn failure | `bugs.md` | Medium |
| BUG-6 | Large-file spawn fails with E2BIG | `bugs.md` | Medium |
| BUG-7 | Duplicate skill warnings | `bugs.md` | Low |
| IMP-1 | Failure summary fields | `improvements.md` | High |
| IMP-2 | Stderr verbosity tiers | `improvements.md` | High |
| IMP-3 | Spawn cancel command | `improvements.md` | Medium |
| IMP-4 | Heartbeat/progress for long spawns | `improvements.md` | Medium |
| IMP-5 | Space-state rules at spawn entry | `improvements.md` | Medium |
| IMP-6 | Finish `run` → `spawn` terminology | `improvements.md` | Low |
| TD-1 | Unify spawn execution lifecycle paths | `tech-debt.md` | High |
| TD-2 | Consolidate space-resolution + @name loading | `tech-debt.md` | High |
| TD-3 | Merge warning/normalization utilities | `tech-debt.md` | Medium |
| TD-4 | Consolidate CLI spawn plumbing tests | `tech-debt.md` | Medium |
| TD-5 | Remove overlapping streaming tests | `tech-debt.md` | Medium |
| TD-6 | Centralize subprocess test helpers | `tech-debt.md` | Medium |

## Active Plans (items tracked there, not here)

These items are already covered by existing plans — not duplicated in the backlog:

- `meridian start` skill injection → `plans/unify-harness-launch.md` Step 0-1
- Agent profiles no default skills → `plans/unify-harness-launch.md` Step 0
- Artifact keys lack space component → `plans/space-plumbing-fix.md` Step 3
- Primary spawn + report policy → `plans/primary-spawn-report-policy.md`

## Structure

- `bugs.md` — Runtime bugs and correctness issues (7 items)
- `improvements.md` — UX and observability improvements (6 items)
- `tech-debt.md` — Code and test cleanup (6 items)
- `_reference/migration-gotchas.md` — Historical notes from `run` → `spawn` migration (not actionable)

## Conventions

- Keep items small, concrete, and testable.
- Link to source files and related plan docs where possible.
- Move items into scoped plan files when actively implementing.
- When a plan fully covers an item, reference the plan in "Active Plans" above instead of duplicating.
