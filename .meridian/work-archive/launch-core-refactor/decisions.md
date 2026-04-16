# Launch Core Refactor Decisions

## D1: Phase 4 Approach

**Context:** Phase 4 rewires the factory boundary to accept raw `SpawnRequest` + `LaunchRuntime` instead of pre-resolved `PreparedSpawnPlan`.

**Decision:** Create a new `build_launch_context()` function that:
1. Handles bypass dispatch first (sole owner of `MERIDIAN_HARNESS_COMMAND` parsing)
2. Runs pipeline stages in fixed order: policies → permissions → prompt → run_inputs → fork (gated by dry_run) → spec → workspace projection → argv → env
3. Returns complete `LaunchContext` (or sum type with bypass variant)

The existing `prepare_launch_context()` will be deprecated/removed once all callers migrate.

**Constraints:**
- Keep transitional compatibility with `ResolvedPrimaryLaunchPlan` until Phase 5 rewires drivers
- Preflight must run in both dry-run and runtime paths for argv parity
