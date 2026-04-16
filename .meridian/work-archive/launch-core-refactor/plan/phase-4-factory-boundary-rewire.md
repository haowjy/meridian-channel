# Phase 4: Factory Boundary Rewire

## Scope

Switch the central launch seam from the current pre-resolved plan input to raw
`SpawnRequest + LaunchRuntime`. Make the factory the sole owner of bypass
dispatch and dry-run/runtime parity, and make the returned `LaunchContext`
complete enough for executors to consume without reconstructing composition.

## Boundaries

- Keep dead-type deletion out of this phase; callers may bridge through
  transitional compatibility shims if needed, but the central factory contract
  must be the new one by phase exit.
- Session-id observation and fork-after-row ordering stay for Phase 5.

## Touched Files and Modules

- `src/meridian/lib/launch/context.py`
- `src/meridian/lib/launch/__init__.py`
- `src/meridian/lib/launch/cwd.py`
- `src/meridian/lib/launch/command.py`
- `src/meridian/lib/launch/process.py` where it depends on the new context
- `tests/launch/test_launch_factory.py`
- Any focused launch tests that assert dry-run or bypass behavior

## Claimed Leaf IDs

- `REQ-SC1`
- `ARCH-I1`
- `ARCH-I8`

## Touched Refactor IDs

- `R06`

## Dependencies

- Phase 3

## Tester Lanes

- `@verifier`
- `@unit-tester`
- `@smoke-tester`

## Exit Criteria

- `build_launch_context()` accepts raw `SpawnRequest` and `LaunchRuntime`;
  drivers no longer need a pre-resolved `PreparedSpawnPlan` to invoke it.
- `_build_bypass_context()` is the sole bypass and
  `MERIDIAN_HARNESS_COMMAND` owner.
- Dry-run and runtime produce the same bypass/runtime argv for the same raw
  request.
- `LaunchContext` is complete executor input; executors do not need to rebuild
  argv/env/perms after the factory returns.
- `uv run ruff check .`
- `uv run pyright`
- Targeted pytest for factory contract and dry-run/bypass parity
- Smoke coverage proves `--dry-run`, primary preview, and normal runtime still
  behave the same from the user's perspective.

