# SOLID Review of Session Changes

## Scope

Reviewed the session changes around:

- agent catalog listing (`agents.list`)
- ad-hoc skill merging for `spawn create` and `spawn continue`
- queued/running spawn lifecycle tracking
- PID persistence, cancellation, and reconciliation
- primary/background launch process updates

## Findings

### Finding 1

- Principle: `O`
- Severity: `High`
- Location: `src/meridian/lib/ops/spawn/api.py` (`_resolve_cancel_pid`, `spawn_cancel_sync`); `src/meridian/lib/launch/runner.py` (`execute_with_finalization` finalization path); `src/meridian/lib/launch/process.py` (`run_harness_process`)
- Issue:
  The session introduced cancellation as a new terminal write path by calling `finalize_spawn_if_active(...)` in `spawn_cancel_sync`, but the normal execution paths still call `finalize_spawn(...)` unconditionally when they unwind. That means `cancelled` is not a durable terminal state: a cancel request can append a `cancelled` event, and then the background worker or primary runner can append a later `failed` or `succeeded` finalize event that wins during event replay.

  The risk is highest for background spawns because `_resolve_cancel_pid()` prefers `worker_pid` over `wrapper_pid` for background runs. In that mode the wrapper process is the component that still owns finalization, so killing only the worker leaves the wrapper alive long enough to write a second terminal event. The new status transition therefore requires coordinated edits across multiple writers instead of being absorbed by one lifecycle abstraction.
- Suggestion:
  Move all terminal writes behind one shared lifecycle helper that only finalizes active spawns, and use it from cancel, child execution, and primary execution paths. For background cancellation, target the wrapper process or process group first, or persist a cancellation intent that the wrapper must honor before attempting its own finalization.

### Finding 2

- Principle: `S`
- Severity: `Medium`
- Location: `src/meridian/lib/ops/spawn/api.py` (`spawn_cancel_sync`)
- Issue:
  `spawn_cancel_sync()` now performs too many responsibilities at once: raw store lookup, status classification, launch-mode interpretation, PID discovery, signal delivery, and state finalization. That concentration makes the behavior fragile because the function bypasses the normal active-spawn reconciliation path and reads the raw record via `spawn_store.get_spawn(...)`.

  As a result, cancellation decisions are made from stale state. A spawn that a reaper pass would already downgrade from `queued`/`running` to `failed`, or upgrade to `succeeded` because a durable report exists, can still be treated here as cancellable. That makes cancel semantics dependent on whether another read path happened to reconcile first.
- Suggestion:
  Split cancellation into smaller helpers such as `load_cancellable_spawn()`, `resolve_cancel_target()`, and `finalize_cancelled()`. The first step should always reconcile active spawns before deciding whether cancellation is still valid, so every command observes the same lifecycle truth.

### Finding 3

- Principle: `O`
- Severity: `Medium`
- Location: `src/meridian/lib/ops/spawn/api.py` (`spawn_stats_sync`); `src/meridian/lib/state/spawn_store.py` (`ACTIVE_SPAWN_STATUSES`, `is_active_spawn_status`); `src/meridian/lib/ops/work.py` (`_ACTIVE_SPAWN_STATUSES`, `work_dashboard_sync`)
- Issue:
  This session correctly introduced an active-status abstraction for `queued` plus `running`, but the migration is incomplete. `spawn_stats_sync()` still increments the active counter only when `row.status == "running"`, so newly queued spawns disappear from the stats even though the rest of the session now treats them as active. Separately, `work.py` still owns a private `_ACTIVE_SPAWN_STATUSES` constant instead of depending on the shared lifecycle helper.

  The abstraction exists, but consumers still need to know the concrete status set. That is exactly the kind of ripple effect the new helper was supposed to eliminate.
- Suggestion:
  Centralize active-status semantics in one shared lifecycle module and require stats, dashboards, doctor, query, and cancel code to use it. If the product needs to distinguish `queued` from `running`, expose separate counters explicitly instead of overloading a single `running` field with half-migrated meaning.

### Finding 4

- Principle: `D`
- Severity: `Low`
- Location: `src/meridian/lib/ops/catalog.py` (`agents_list_sync`); `src/meridian/lib/catalog/agent.py` (`load_agent_profile`, `builtin_profiles`)
- Issue:
  `agents_list_sync()` reimplements bundled-profile discovery and builtin fallback locally instead of depending on a single profile-resolution abstraction from `catalog.agent`. The code comments explicitly say it "mirrors" `load_agent_profile()` logic, which is a warning sign: mirrored policy drifts as soon as one side changes precedence rules, filtering, or error handling.

  The new `agents.list` surface therefore depends on concrete scan order and fallback details instead of a shared catalog contract. That weakens the harness-agnostic, data-driven design the repository is aiming for.
- Suggestion:
  Extract a shared `list_agent_profiles(...)` or `iter_resolved_agent_profiles(...)` helper in `src/meridian/lib/catalog/agent.py` and have both `agents_list_sync()` and `load_agent_profile()` depend on it. That keeps discovery policy in one place and makes future profile-source changes additive instead of duplicative.

## Summary Table

| Principle | Grade | One-line rationale |
| --- | --- | --- |
| `S` | `B-` | Spawn cancellation now mixes reconciliation, process targeting, signaling, and state mutation in one path. |
| `O` | `C+` | Active-status and cancellation changes are only partially absorbed by shared abstractions, so consumers still need manual updates. |
| `L` | `B` | The new queued/running lifecycle mostly composes with existing callers, but some consumers still assume the older running-only model. |
| `I` | `A-` | The new CLI and payload additions stay relatively focused and do not introduce obvious interface bloat. |
| `D` | `C+` | Catalog and cancellation flows still depend on concrete discovery/finalization details instead of shared lifecycle abstractions. |

## Verification

- Reviewed the current working tree diff and surrounding implementation paths.
- No runtime reproduction or test execution was performed for this review.
