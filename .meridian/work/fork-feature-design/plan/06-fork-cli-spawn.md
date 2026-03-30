# Phase Fork 1: CLI Surface — --fork on Spawn Command

## Scope

Decouple `--fork` from `--continue` on the spawn command. Change `--fork` from a boolean modifier to a standalone string flag that accepts a session or spawn reference. Wire validation for mutual exclusivity with `--continue`, `--from`, and cross-harness mismatch.

## Intent

After this phase, `meridian spawn --fork p42 -p "new direction"` works as a standalone command (not `--continue p42 --fork`). The old boolean `--fork` syntax is removed entirely — CLAUDE.md says "no backwards compatibility needed."

## Files to Modify

- **`src/meridian/cli/spawn.py`** — Change CLI parameter:
  ```python
  # Before
  fork: Annotated[bool, Parameter(name="--fork", ...)] = False

  # After
  fork_from: Annotated[str | None, Parameter(name="--fork", help="Fork from a session or spawn reference.")] = None
  ```
  When `--fork` is provided:
  1. Resolve via `resolve_session_reference()` (from Prep 4)
  2. Validate mutual exclusivity with `--continue` and `--from`
  3. Validate harness compatibility (source harness must match `--harness` if specified)
  4. Build `SpawnCreateInput` with `continue_harness_session_id`, `continue_harness`, `continue_fork=True`
  5. Also pass `forked_from_chat_id` from the resolved reference

  When old syntax `--continue p5 --fork` is used (now impossible at parser level since `--fork` takes a string), add a helpful error if someone tries `--continue p5 --fork p5`.

- **`src/meridian/lib/ops/spawn/models.py`** — Add `forked_from_chat_id: str | None = None` to `SpawnCreateInput` so lineage flows downstream.

## Dependencies

- **Requires**: Prep 5 (validation hardening), Prep 4 (shared resolver).
- **Produces**: Working `meridian spawn --fork <ref>` CLI surface. Fork 2 mirrors this pattern for root. Fork 5 consumes `forked_from_chat_id` in the pipeline.

## Interface Contract

### CLI validation rules:
```
--fork + --continue  → Error: "Cannot combine --fork with --continue."
--fork + --from      → Error: "Cannot combine --fork with --from (MVP limitation)."
--fork + --harness   → Validate source harness matches, or error:
                       "Cannot fork across harnesses: source is 'claude', target is 'codex'."
--fork + --model     → Allowed (override source model)
--fork + --agent     → Allowed (override source agent)
--fork + --yolo      → Allowed
--fork + --work      → Allowed (attach to different work item)
```

### SpawnCreateInput changes:
```python
class SpawnCreateInput(BaseModel):
    # ... existing ...
    continue_fork: bool = False
    forked_from_chat_id: str | None = None  # NEW — lineage for session event
```

### Metadata inheritance (from design spec):
1. CLI flags (`--model`, `--agent`, `--work`) take highest priority
2. If `--agent` is overridden, its profile's skills replace inherited skills
3. If no CLI override, inherit from the resolved source metadata
4. If source has no metadata (raw UUID ref), fall back to config/profile defaults

## Patterns to Follow

- See existing `_spawn_create()` function in `cli/spawn.py` for how `--continue` is handled today.
- See `SpawnContinueInput` for how fork=True currently flows. The new path bypasses `SpawnContinueInput` entirely — it goes directly to `SpawnCreateInput` with the resolved values.

## Constraints

- Do NOT touch the root command or harness adapters — those are separate phases.
- Do NOT implement fork logic in the launch pipeline — that's Fork 5. This phase wires `continue_fork=True` through existing plumbing.
- The spawn output JSON should include `forked_from` field when fork is used (or defer to Fork 6 if the output change is coupled to other output work).
- Remove the old boolean `--fork` parameter entirely. No backward compat alias.

## Verification Criteria

- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes with 0 errors
- [ ] `uv run pytest-llm` passes
- [ ] `meridian spawn --fork p42 -p "test" --dry-run` resolves the reference and shows the planned command
- [ ] `meridian spawn --fork p42 --continue p42 -p "test"` errors clearly
- [ ] `meridian spawn --fork p42 --from p41 -p "test"` errors clearly
- [ ] `meridian spawn --fork p42 -m gpt -p "test" --dry-run` shows model override
- [ ] `meridian spawn --continue p42 -p "test"` still works (not broken by removal of bool --fork)
