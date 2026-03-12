# Lifecycle Unification Plan

## Overview

Three work streams that reinforce each other:

1. **Phase 1 -- Bug Fixes** (2 bugs, immediately shippable)
2. **Phase 2 -- Lifecycle Unification** (one state machine for all spawn types)
3. **Phase 3 -- SOLID Refactor** (8 items from the audit, sequenced after Phase 2)

Design principle: primary launch and child spawn now have the same lifecycle shape because I/O is controlled. The PTY-based sync path in `process.py` and the async subprocess path in `runner.py` are both mechanism variations on the same state machine: `queued -> running -> {succeeded, failed, cancelled}`.

---

## Phase 1: Bug Fixes

### Bug 1: Primary spawn unlabeled in dashboard

**Root cause:** Primary spawns are created with `kind="primary"` but no `work_id` or `desc`. The common flow is: user starts a session (no work item yet), then later runs `work start "feature"` — but that only updates session state, not the already-running primary spawn record. Dashboard groups by `spawn.work_id` and labels by `spawn.desc`, so the primary spawn falls under "(no work)" with no label.

**The real fix is backfill on work change, not launch-time propagation.** Adding fields to `LaunchRequest` only helps the rare case where a work item already exists before launch. The common case is `work start` happening after the primary spawn is already running.

**Steps:**

1. **Add `desc` and `work_id` to `SpawnUpdateEvent`** in `src/meridian/lib/state/spawn_store.py`
   - Enables retroactive backfill of metadata on already-running spawns.
   - Update `_record_from_events()` to apply these fields on update events (same `if event.X is not None else current.X` pattern).

2. **Annotate primary spawn on `work start` / `work switch`** in `src/meridian/lib/ops/work.py`
   - After `_set_active_work_id(...)`, find the active `kind="primary"` spawn for the current `chat_id`.
   - Write `update_spawn(state_root, spawn_id, work_id=item.name)` to associate it.
   - This is the core fix — when the user says "I'm working on X", the running primary spawn gets tagged.

3. **Dashboard fallback to `kind`** in `src/meridian/lib/ops/work.py`
   - `_spawn_desc()` falls back to `spawn.kind` when `desc` is empty.
   - Primary spawns show "(primary)" rather than blank, even for old records.

4. **Tests:**
   - `test_spawn_store.py`: verify SpawnUpdateEvent backfills desc/work_id
   - `test_work.py`: verify `work start` annotates the active primary spawn
   - `test_work.py`: verify `_spawn_desc` fallback to kind

**Parallelism:** Steps 1-2 are sequential (2 depends on 1). Step 3 is independent. Step 4 depends on all.

---

### Bug 2: spawn wait false failure on harness_completed

**Root cause:** `spawn wait` polls `read_spawn_row()` which runs the reaper. Reaper checks orphan (dead PID) BEFORE durable report completion. If harness exits but runner hasn't finalized yet, reaper stamps `failed/orphan_run`. Additionally, successful finalize events don't clear stale errors due to `exclude_none=True` serialization.

**Steps:**

1. **Reorder reaper checks** in `src/meridian/lib/state/reaper.py`
   - In `_reconcile_background_spawn()`: move `has_durable_report_completion` check BEFORE orphan check.
   - In `_reconcile_foreground_spawn()`: same reorder.

2. **Fix stale error in event reduction** in `src/meridian/lib/state/spawn_store.py`
   - In `_record_from_events()` finalize handler: when `event.status == "succeeded"`, force `error = None`.
   ```python
   "error": (
       None if event.status == "succeeded"
       else event.error if event.error is not None
       else current.error
   ),
   ```

3. **Tests:**
   - `test_reaper.py`: spawn with durable report + dead PID reconciles to succeeded
   - `test_spawn_store.py`: succeeded finalize clears prior orphan_run error

**Parallelism:** Steps 1 and 2 are independent. Step 3 depends on both.

---

## Phase 2: Lifecycle Unification

**Goal:** One state machine for all spawn types (primary, child-background, child-foreground).

**Current state:**
- `launch/process.py` (566 LOC) — primary launch, inline lifecycle
- `ops/spawn/execute.py` (964 LOC) — child spawn init + launch, inline lifecycle
- `launch/runner.py` (886 LOC) — shared execution loop, inline lifecycle
- `core/spawn_lifecycle.py` (43 LOC) — terminal state resolution only
- `state/reaper.py` (508 LOC) — read-path state machine

### Step 2.1: Define unified lifecycle envelope

Expand `src/meridian/lib/core/spawn_lifecycle.py`:

```python
class SpawnLifecycleEnvelope:
    """Manages start -> running -> terminal lifecycle for any spawn type."""

    def __init__(self, state_root: Path, spawn_id: SpawnId): ...

    def mark_running(self, *, launch_mode: LaunchMode,
                     wrapper_pid: int | None = None,
                     worker_pid: int | None = None) -> None: ...

    def finalize(self, *, exit_code: int, failure_reason: str | None = None,
                 durable_report_completion: bool = False,
                 terminated_after_completion: bool = False,
                 duration_secs: float | None = None,
                 usage: TokenUsage | None = None) -> SpawnStatus: ...
```

The envelope wraps `spawn_store.mark_spawn_running()`, `resolve_execution_terminal_state()`, and `spawn_store.finalize_spawn()`. It does NOT own the subprocess — only the state transitions.

### Step 2.2: Refactor `process.py` to use envelope

Replace inline lifecycle in `run_harness_process()` (~30 lines) with envelope calls (~5 lines).

### Step 2.3: Refactor `runner.py` to use envelope

Replace lifecycle in `execute_with_finalization()` finally block with `envelope.finalize(...)`.

### Step 2.4: Refactor `execute.py` to use envelope

`_init_spawn()` returns a `_SpawnContext` that holds a `SpawnLifecycleEnvelope`. Callers use envelope instead of manual state transitions.

### Step 2.5: Refactor reaper to share terminal-state logic

Reaper's `_finalize_completed_report()` and `_finalize_failed()` use the same finalization path as the envelope.

### Step 2.6: Tests

- Lifecycle envelope unit tests (queued->running->succeeded, idempotent finalize, etc.)
- Verify existing tests pass with refactored paths

**Sequencing:** 2.1 first, then {2.2, 2.3, 2.4, 2.5} in parallel, then 2.6.

**Estimated scope:** ~200 lines new in `spawn_lifecycle.py`, ~90 lines removed across launcher files. Net -50 to -80 lines + much better cohesion.

---

## Phase 3: SOLID Refactor

Ordered by priority. Dependencies on Phase 2 noted.

### 3.1: Move `format_helpers` to lib layer *(No dependencies, trivial)*

Move `tabular()` and `kv_block()` from `meridian.cli.format_helpers` to `meridian.lib.core.format_helpers`. Update 6 lib-layer imports. Keep CLI re-export.

### 3.2: Consolidate `ACTIVE_SPAWN_STATUSES` *(No dependencies, trivial)*

Replace `_ACTIVE_SPAWN_STATUSES` in `work.py` with import from `spawn_store.py`.

### 3.3: Break up `build_create_payload()` *(After Phase 2)*

Extract ~6 focused helpers: `_resolve_runtime_view()`, `_resolve_agent_and_defaults()`, `_resolve_skills()`, `_resolve_continuation()`, `_build_permissions()`, `_compose_prompt()`. Main function becomes ~30-line orchestrator.

### 3.4: Fix DirectAdapter DIP violation *(After Phase 2)*

Inject tool registry via constructor rather than importing `ops.manifest` directly. Define `ToolDefinitionSource` protocol in harness layer.

### 3.5: Narrow HarnessAdapter protocol *(LAST, highest risk)*

Split into `HarnessLauncher`, `HarnessExtractor`, `HarnessSessionManager`. `HarnessAdapter` becomes composite. `BaseHarnessAdapter` maps cleanly.

### 3.6: Manifest registration via decorator *(DEFER)*

Current explicit manifest is inspectable and follows "Knowledge in Data" principle. Only pursue if team finds single-file-edit painful.

### 3.7: Extract `format_text` from domain models *(After 3.1)*

Move implementations to formatting layer. Domain models stay pure data.

### 3.8: Consolidate `_spawn_desc` fallback *(After Phase 1)*

Add `display_desc` property on `SpawnRecord` instead of each consumer re-implementing fallback.

---

## Execution Order

```
Phase 1 (Bug Fixes) -- Immediate
  Bug 1: steps 1-2 || steps 3-4 -> step 5
  Bug 2: step 1 || step 2 -> step 3

Phase 2 (Lifecycle Unification) -- After Phase 1
  2.1 -> {2.2, 2.3, 2.4, 2.5} parallel -> 2.6

Phase 3 (SOLID Refactor) -- Mixed timing
  3.1, 3.2: anytime (no dependencies)
  3.3, 3.4: after Phase 2
  3.7: after 3.1
  3.8: after Phase 1
  3.5: LAST
  3.6: DEFER
```

## Risk Assessment

- **Phase 1:** Low risk. Narrow fixes, clear root causes.
- **Phase 2:** Medium risk. Envelope wraps existing paths, doesn't own subprocesses. Mitigate by testing each refactored path incrementally.
- **Phase 3:** Variable. 3.1/3.2 trivial. 3.3/3.4 moderate. 3.5 highest risk (protocol boundary change).
