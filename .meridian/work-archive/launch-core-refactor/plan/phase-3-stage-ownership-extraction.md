# Phase 3: Stage Ownership Extraction

## Scope

Extract the composition stages into their owned modules so the factory can call
real stage functions with one owner each. This phase moves logic, not boundary
ownership: it prepares the launch core for the later raw-input factory switch.

## Boundaries

- Keep the current top-level factory boundary working while logic moves.
- Do not yet change drivers to call the factory differently.
- `harness/adapter.py` must move toward contracts-only; do not leave new
  mechanism logic behind while extracting stages.

## Touched Files and Modules

- `src/meridian/lib/launch/policies.py`
- `src/meridian/lib/launch/permissions.py`
- `src/meridian/lib/launch/prompt.py`
- `src/meridian/lib/launch/run_inputs.py` (new)
- `src/meridian/lib/launch/command.py`
- `src/meridian/lib/launch/env.py`
- Source logic owners being reduced:
  `src/meridian/lib/launch/resolve.py`,
  `src/meridian/lib/safety/permissions.py`
- `src/meridian/lib/harness/adapter.py`
- Focused factory-stage tests and affected launch/harness unit tests

## Claimed Leaf IDs

- `ARCH-I6`
- `ARCH-I7`
- `ARCH-I9`

## Touched Refactor IDs

- `R06`

## Dependencies

- Phase 2

## Tester Lanes

- `@verifier`
- `@unit-tester`
- `@smoke-tester`

## Exit Criteria

- Each named pipeline stage lives in its owning module with real definitions,
  not re-export shells.
- `harness/adapter.py` contains contracts only for the extracted concerns; no
  new concrete env/permission/session-observation logic is introduced there.
- The workspace-projection seam is explicitly represented between spec
  resolution and argv build, even if harness-specific mechanics remain out of
  scope for this work item.
- `uv run ruff check .`
- `uv run pyright`
- Targeted pytest covering stage behavior and impacted launch/harness tests
- Smoke coverage proves launch behavior is unchanged after the logic move.

