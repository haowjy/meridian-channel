# Launch Core Refactor Requirements

## Problem Statement

The launch subsystem has structural debt that impairs maintainability, testability, and extensibility. The hexagonal shell landed — `build_launch_context()` exists and `LaunchContext` is a sum type — but the core did not. Composition logic remains scattered across driving adapters, creating multiple code paths that should converge through a single factory.

## Goals

1. **Single composition seam.** All launch composition passes through one factory (`build_launch_context()`). Driving adapters construct raw input (`SpawnRequest`) and call the factory; they do not perform composition themselves.

2. **Typed pipeline with explicit stages.** The factory executes a fixed, named pipeline: policy resolution, permission resolution, prompt composition, run-input aggregation, fork materialization, spec resolution, workspace projection, argv build, env build. Each stage has one owner module.

3. **Serializable input artifact.** The worker prepare→execute boundary persists a `SpawnRequest` JSON blob — no live objects, no `arbitrary_types_allowed`. Composition is reconstructed at execute time, not cached from prepare time.

4. **Behavioral test coverage over heuristic guards.** The current `rg`-count CI guards pass while the invariants they protect are structurally false. Replace with behavioral factory tests that pin actual composition, plus a semantic drift gate for novel violations.

5. **Session-ID observation through adapter seam.** `observe_session_id()` is implemented per-adapter, called once post-execution by the driving adapter. The old `extract_latest_session_id` path and inline executor scrapes are deleted.

6. **Fork-after-row ordering.** Fork materialization happens inside the factory, after the spawn row exists, in every driver path. No orphan fork window.

## Non-Goals

- Per-harness workspace projection mechanics (separate work item).
- Config file relocation or loader changes.
- Popen-fallback session-ID observability (tracked by issue #34).
- Claude session-accessibility symlinking.

## Success Criteria

- `build_launch_context()` accepts raw `SpawnRequest` + `LaunchRuntime`; no pre-resolved `PreparedSpawnPlan`.
- Driving adapters contain zero calls to the prohibition list (resolver constructors, adapter composition methods, etc.).
- `SpawnRequest` round-trips via `model_dump_json` / `model_validate_json` without escape hatches.
- Behavioral factory tests pin each major invariant (see refactors.md test list).
- CI architectural drift gate blocks PRs that violate declared invariants.
- `scripts/check-launch-invariants.sh` deleted; heuristic guards replaced by semantic verification.

## Dependencies

- **R01 (ProjectPaths extraction):** R06's `LaunchRuntime` carries `project_paths: ProjectPaths`. R01 must land first so this type exists.

## Prior Art

R06 was attempted once and reverted due to a Codex prompt-truncation bug (coder briefs silently truncated at 50 KiB). The design is sound; implementation failed due to tooling, not architecture. This work item picks up from the validated design, not from scratch.

## Constraints

- Implementation MUST run against meridian-cli ≥ v0.0.30 (post-Fix-A).
- Net pytest count must be non-negative across the refactor series.
- Per-phase smoke baseline required before implementation opens.
