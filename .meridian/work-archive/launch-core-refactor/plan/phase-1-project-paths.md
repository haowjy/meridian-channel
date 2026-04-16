# Phase 1: Project Paths Extraction

## Scope

Create the `ProjectPaths` prerequisite required by `LaunchRuntime` and update
the current launch/runtime callers to consume that typed path bundle instead of
passing project-level paths as unrelated raw `Path` values.

## Boundaries

- This phase is prerequisite plumbing only. It does not introduce
  `SpawnRequest`, change factory ownership, or rewire drivers.
- Keep behavior identical. The goal is to make `project_paths` available as an
  explicit runtime input so later phases can depend on it.

## Touched Files and Modules

- `src/meridian/lib/state/paths.py`
- `src/meridian/lib/core/context.py` or the canonical shared runtime-context
  module chosen by the implementation
- Current launch/runtime callers that need typed project paths:
  `src/meridian/lib/launch/context.py`,
  `src/meridian/lib/launch/process.py`,
  `src/meridian/lib/ops/spawn/execute.py`,
  `src/meridian/lib/app/server.py`
- Focused tests for path-resolution and call-site updates

## Claimed Leaf IDs

- `DEP-R01`

## Touched Refactor IDs

- `DEP-R01`

## Dependencies

- None

## Tester Lanes

- `@verifier`
- `@unit-tester`
- `@smoke-tester`

## Exit Criteria

- `ProjectPaths` exists in one canonical shared module and is the runtime-path
  bundle later phases will place on `LaunchRuntime`.
- No caller that will participate in R06 still depends on ad hoc project-path
  tuples for the values now carried by `ProjectPaths`.
- `uv run ruff check .`
- `uv run pyright`
- Targeted pytest for the touched path/runtime tests
- Smoke coverage proves existing launch entry points still resolve execution
  roots correctly after the extraction.

