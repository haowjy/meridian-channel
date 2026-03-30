# Phase Fork 6: User-Facing Output + Smoke Tests

## Scope

Polish the JSON output for fork commands and write the smoke test guide. Ensure both root and spawn fork commands produce structured output with fork-specific fields (forked_from, new chat_id, resume command).

## Intent

After this phase, fork is user-ready. The output tells users what happened (forked from X, new session Y, resume with Z), and there's a comprehensive smoke test guide for manual verification.

## Files to Modify

- **`src/meridian/cli/main.py`** — Update `PrimaryLaunchOutput` model:
  ```python
  class PrimaryLaunchOutput(BaseModel):
      # ... existing fields ...
      forked_from: str | None = None  # NEW — source reference for fork
  ```
  Update `_run_primary_launch()` to set `forked_from` when fork mode is active.
  Update `format_text()` to include fork info in human-readable output.

- **`src/meridian/cli/spawn.py`** — Update spawn output to include `forked_from` field when fork was used. This may flow through `SpawnActionOutput` or be added at the CLI layer.

- **`src/meridian/lib/ops/spawn/api.py`** or **`models.py`** — If `SpawnActionOutput` needs a `forked_from` field, add it here.

- **`tests/smoke/fork.md`** (NEW) — Comprehensive smoke test guide covering all FORK-1 through FORK-19 scenarios from the design spec.

## Dependencies

- **Requires**: Fork 5 (pipeline integration complete), Fork 2 (root CLI complete).
- **Produces**: Polished user-facing output and smoke test documentation.

## Interface Contract

### Root command output (`meridian --fork c367`):
```json
{
  "message": "Session forked.",
  "forked_from": "c367",
  "exit_code": 0,
  "continue_ref": "c402",
  "resume_command": "meridian --continue c402"
}
```

Human-readable:
```
Session forked from c367.
To continue with meridian:
meridian --continue c402
```

### Spawn command output (`meridian spawn --fork c367 -p "do X"`):
```json
{
  "spawn_id": "p45",
  "chat_id": "c402",
  "forked_from": "c367",
  "status": "running"
}
```

### Smoke test coverage (from design spec):
```
FORK-1:  spawn --fork <spawn_id> -p "prompt" → new spawn + new chat_id
FORK-2:  --fork <session_id> → new interactive session
FORK-3:  spawn --fork <session_id> -p "prompt" → session ref fork
FORK-4:  spawn --fork + --from → error
FORK-5:  --fork + --continue → error
FORK-6:  spawn --fork + --model override → uses specified model
FORK-7:  spawn --fork + --agent override → uses specified agent
FORK-8:  spawn --fork + --yolo → works
FORK-9:  spawn --fork + --work override → different work item
FORK-10: Fork with each harness (claude, codex, opencode)
FORK-11: Source session untouched after fork
FORK-12: Fork nonexistent session → clear error
FORK-13: Fork with unsupported harness → clear error
FORK-14: --fork + --dry-run → preview without executing
FORK-15: spawn --fork + --harness cross-harness → error
FORK-16: Fork spawn with no harness_session_id → error
FORK-17: --continue + --fork (old syntax) → helpful error
FORK-18: Fork with raw harness UUID → works, no lineage
FORK-19: Fork prompt guidance verified
```

## Patterns to Follow

- See existing `PrimaryLaunchOutput.format_text()` for human-readable output pattern.
- See `tests/smoke/` for existing smoke test guide format.
- See `SpawnActionOutput.to_wire()` for how spawn results are serialized.

## Constraints

- Do NOT change any pipeline logic — that's all done.
- Focus on output formatting and test documentation.
- Smoke tests are markdown guides, not automated tests. Follow the existing format in `tests/smoke/`.

## Verification Criteria

- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes with 0 errors
- [ ] `uv run pytest-llm` passes
- [ ] `meridian --fork c1 --dry-run` shows forked_from in output
- [ ] Spawn fork dry-run shows forked_from in JSON output
- [ ] `tests/smoke/fork.md` covers all 19 scenarios from design spec
- [ ] Human-readable output clearly communicates what happened
