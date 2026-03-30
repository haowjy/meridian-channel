# Phase Prep 5: Fail Hard on Missing harness_session_id for Continue/Fork

## Scope

Today `--continue` silently starts a fresh session if the source has no `harness_session_id`. For fork this is catastrophic — you'd silently create a "fork" with no conversation history. Add explicit validation that errors immediately when the source reference resolves but has no harness_session_id.

## Intent

Prevent silent data loss. After this phase, attempting to continue or fork from a session/spawn with no recorded harness_session_id fails fast with a clear error message instead of silently degrading.

## Files to Modify

- **`src/meridian/lib/ops/spawn/prepare.py`** — In the fork/continue resolution block (around line ~263), add explicit check: if `requested_harness_session_id` is empty/None AND the source was a tracked reference (not a raw UUID), raise or set an error instead of silently proceeding.

- **`src/meridian/lib/ops/spawn/api.py`** — In `spawn_continue_sync()`, after resolving the source spawn, validate that `source_session_id` is not None before passing to `SpawnCreateInput`. Error message: `"Spawn '{spawn_id}' has no recorded session — cannot continue/fork."`

- **`src/meridian/lib/ops/reference.py`** — Ensure `ResolvedSessionReference` clearly reports when `harness_session_id` is None so callers can distinguish "not found" from "found but no session ID."

## Dependencies

- **Requires**: Prep 4 (shared resolver is in place).
- **Produces**: Hard validation that fork phases can rely on — if a reference resolves, it has a usable harness_session_id.

## Interface Contract

Error messages must be clear and actionable:

```
Error: Spawn 'p42' has no recorded session — cannot continue.
  The spawn may have been killed before the harness reported its session ID.

Error: Session 'c367' has no recorded harness session — cannot fork.
  The session may not have been started through meridian.
```

## Patterns to Follow

- See existing validation in `prepare.py` lines 263-285 where `continuation_warning` is set. Convert to hard errors for the "source exists but has no session ID" case.
- Keep the existing soft warning for harness mismatch (that's a different situation — the session exists but is owned by a different harness).

## Constraints

- Do NOT break existing `--continue` behavior for valid references. Only add errors for the "resolved but no harness_session_id" case.
- The `--continue` with a raw UUID that nobody recognizes should still produce the existing warning, not a hard error (the user might know what they're doing).
- Do NOT add fork-specific validation yet. Just harden the shared path.

## Verification Criteria

- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes with 0 errors
- [ ] `uv run pytest-llm` passes
- [ ] `meridian spawn --continue pNNN -p "test"` still works for spawns with valid session IDs
- [ ] Attempting to continue from a spawn with no harness_session_id produces a clear error
