# Phase Fork 5: Launch Pipeline Integration

## Scope

Thread `SessionMode.FORK` through the launch pipeline. This is the central integration phase — it connects the CLI surface (Fork 1, Fork 2) to the harness adapters (Fork 3, Fork 4) via the launch plan and process layers.

## Intent

After this phase, fork actually works end-to-end. The pipeline correctly:
1. Seeds sessions with fork semantics (new meridian session, existing harness session)
2. Includes full content (skills, bootstrap) for fork (not suppressed like resume)
3. Injects fork-specific prompt guidance (not continuation guidance)
4. Creates new chat_id with forked_from_chat_id lineage
5. Calls `fork_session()` for adapters that need it (Codex)
6. Rejects fork with MERIDIAN_HARNESS_COMMAND override

## Files to Modify

- **`src/meridian/lib/launch/plan.py`** — Update `resolve_primary_launch_plan()`:
  - Read `request.session_mode` and `request.continue_fork`
  - For FORK mode: `is_resume=False` in `seed_session()` call (fork gets new session)
  - For FORK mode: `is_resume=False` in `filter_launch_content()` (full content)
  - In the MERIDIAN_HARNESS_COMMAND override path: reject fork with clear error message
  - Use the unified `_build_run_params()` (from Prep 2) and set `continue_fork=True`

- **`src/meridian/lib/launch/types.py`** — Add fork guidance:
  ```python
  _FORK_GUIDANCE = (
      "You are working in a forked Meridian session — a branch from a prior conversation. "
      "You have the full context from the original session. The user wants to explore "
      "a different direction from here. Do not repeat completed work."
  )
  ```
  Update `build_primary_prompt()` to use `_FORK_GUIDANCE` when `session_mode == SessionMode.FORK`.

- **`src/meridian/lib/launch/process.py`** — Update `run_harness_process()`:
  - Pass `forked_from_chat_id` to `session_scope()` (from Prep 3)
  - For fork: do NOT pass `continue_chat_id` (must allocate new chat_id)
  - Call `fork_session()` on adapter before building command, when adapter requires it
  - Skip `fork_session()` on dry_run
  - Replace `continue_harness_session_id` in run_params with the new session ID returned by `fork_session()`

- **`src/meridian/lib/launch/session_scope.py`** — Already accepts `forked_from_chat_id` (from Prep 3). No additional changes.

- **`src/meridian/lib/ops/spawn/prepare.py`** — Update fork handling for spawn path:
  - When `continue_fork=True`, the pipeline should call `fork_session()` for Codex before `build_command()`
  - Ensure `forked_from_chat_id` flows from `SpawnCreateInput` through to the session event

- **`src/meridian/lib/launch/runner.py`** (if it exists as a separate module) — Thread fork parameters through.

## Dependencies

- **Requires**: Fork 1 (spawn CLI), Fork 3 (Claude/OpenCode adapters), Fork 4 (Codex adapter).
- **Produces**: Working end-to-end fork pipeline. Fork 6 adds output polish and smoke tests.

## Interface Contract

### Fork launch mode rules (from design spec):

| Launch stage | Fresh | Resume | Fork |
|---|---|---|---|
| `seed_session()` | `is_resume=False` | `is_resume=True` | `is_resume=False` |
| `filter_launch_content()` | Full content | Skip skills/bootstrap | Full content |
| Prompt guidance | None | `_CONTINUATION_GUIDANCE` | `_FORK_GUIDANCE` |
| `start_session()` | New `chat_id` | Reuse `chat_id` | New `chat_id` + `forked_from_chat_id` |
| `harness_session_id` | None | Source ID | Source ID (with fork flag) |

### Key decision points in plan.py:

```python
# Line ~201-205: seed_session
is_resume = request.session_mode == SessionMode.RESUME
# Fork: is_resume=False → new session seed

# Line ~258: filter_launch_content
is_resume = request.session_mode == SessionMode.RESUME
# Fork: is_resume=False → full content included

# Line ~128: build_primary_prompt
# Already uses session_mode from Prep 1
```

### Key decision points in process.py:

```python
# Line ~250-267: session_scope
# Fork: chat_id=None (new), forked_from_chat_id=resolved.source_chat_id

# Before build_command:
if plan.request.continue_fork and hasattr(plan.adapter, 'fork_session'):
    new_session_id = plan.adapter.fork_session(plan.run_params.continue_harness_session_id)
    # Update run_params with new session ID
```

### MERIDIAN_HARNESS_COMMAND rejection:
```python
if override and request.continue_fork:
    raise ValueError(
        "Cannot use --fork with MERIDIAN_HARNESS_COMMAND override. "
        "Fork requires native harness adapter support."
    )
```

### Codex fork_session integration in spawn pipeline:
The spawn pipeline in `ops/spawn/` also needs the `fork_session()` call. The design places `fork_session()` on the adapter, and the pipeline calls it before `build_command()`. The call site should be in the spawn executor (wherever `build_command()` is called), not in `prepare.py`.

## Patterns to Follow

- See how `is_resume` is checked throughout `plan.py` and `process.py`. Fork adds a third case to each check.
- See how `session_scope()` is called in `process.py` (line ~250) with `chat_id=plan.request.continue_chat_id`.
- See how `build_command()` is called and how its result flows to process execution.

## Constraints

- Do NOT change CLI parsing — that's done in Fork 1 and Fork 2.
- Do NOT change adapter `build_command()` implementations — that's Fork 3 and Fork 4.
- The `fork_session()` call must happen BEFORE `build_command()` for Codex, since it returns a new session ID that becomes the resume target.
- `fork_session()` must be skipped on `dry_run=True`.
- For dry_run with Codex fork, show the planned resume command with a placeholder or the source session ID.

## Verification Criteria

- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes with 0 errors
- [ ] `uv run pytest-llm` passes
- [ ] Fork launch produces `_FORK_GUIDANCE` in prompt (not `_CONTINUATION_GUIDANCE`)
- [ ] Fork launch creates new chat_id (not source's)
- [ ] Fork launch records `forked_from_chat_id` in session start event
- [ ] Fork with MERIDIAN_HARNESS_COMMAND errors clearly
- [ ] `seed_session(is_resume=False)` for fork
- [ ] `filter_launch_content(is_resume=False)` for fork (full content)
- [ ] Codex fork calls `fork_session()` before `build_command()`
- [ ] dry_run does NOT call `fork_session()`
