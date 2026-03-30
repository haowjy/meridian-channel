# Phase Fork 2: CLI Surface — --fork on Root Command

## Scope

Add `--fork <ref>` to the root command and harness shortcut commands (`meridian claude`, `meridian codex`, `meridian opencode`). Wire through to `LaunchRequest` using `SessionMode.FORK`.

## Intent

After this phase, `meridian --fork c367` launches a new interactive session branched from c367's conversation history. The original session is untouched.

## Files to Modify

- **`src/meridian/cli/main.py`** — Add `--fork` parameter to `root()` function and `_register_harness_shortcut_command()`:
  ```python
  fork_ref: Annotated[
      str | None,
      Parameter(name="--fork", help="Fork from a session or spawn reference."),
  ] = None
  ```

  Update `_run_primary_launch()`:
  - Accept `fork_ref: str | None = None` parameter
  - When `fork_ref` is provided:
    1. Validate mutual exclusivity with `--continue` (error if both set)
    2. Resolve via `resolve_session_reference()`
    3. Set `session_mode=SessionMode.FORK` on `LaunchRequest`
    4. Pass `continue_harness_session_id` (from resolved source)
    5. Pass `continue_fork=True`
    6. Pass `forked_from_chat_id` (from resolved source's chat_id)
    7. Do NOT pass `continue_chat_id` — fork creates a new chat_id
    8. Allow `--model` and `--agent` (unlike `--continue` which prohibits them)
  - Validate harness compatibility: fork can't cross harnesses
  - Update `PrimaryLaunchOutput` for fork: message="Session forked.", include forked_from field

- **`src/meridian/lib/launch/types.py`** — Add `continue_fork: bool = False` to `LaunchRequest` (this may already be partially done by Prep 1).

## Dependencies

- **Requires**: Fork 1 (patterns established for spawn CLI), Prep 1 (SessionMode enum).
- **Produces**: Complete root CLI surface for fork. Fork 5 threads this through the launch pipeline.

## Interface Contract

### CLI validation rules (same as spawn, adapted for root):
```
--fork + --continue → Error: "Cannot combine --fork with --continue."
--fork + --model    → Allowed (override inherited model — unlike --continue which blocks --model)
--fork + --agent    → Allowed (override inherited agent)
--fork + --harness  → Validate source harness matches
```

### LaunchRequest additions:
```python
class LaunchRequest(BaseModel):
    # ... existing ...
    session_mode: SessionMode = SessionMode.FRESH  # from Prep 1
    continue_fork: bool = False                     # NEW
    forked_from_chat_id: str | None = None          # NEW
```

### Output for fork:
```python
PrimaryLaunchOutput(
    message="Session forked.",
    forked_from="c367",        # NEW field
    exit_code=...,
    continue_ref="c402",       # The NEW session's chat_id
    resume_command="meridian --continue c402",
)
```

### Critical: Do NOT reuse source chat_id

When fork is active, `continue_chat_id` must be `None` so that `session_scope()` allocates a new `chat_id` via `reserve_chat_id()`. Passing the source's `chat_id` would reopen the original session.

## Patterns to Follow

- See how `--continue` is handled in `_run_primary_launch()` (lines 492-568 of `cli/main.py`).
- See `_register_harness_shortcut_command()` (line 594) for how shortcut commands mirror root parameters.
- Fork differs from continue: `fresh` state depends on `SessionMode`, `--model`/`--agent` are allowed.

## Constraints

- Do NOT implement the launch pipeline fork logic — that's Fork 5. This phase wires the CLI flags through to `LaunchRequest`.
- The harness shortcut commands must get `--fork` too (same as they have `--continue`).
- Keep `_ResolvedContinueTarget` or replace with `ResolvedSessionReference` from the shared resolver — either way, the root command must go through the shared resolver from Prep 4.

## Verification Criteria

- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes with 0 errors
- [ ] `uv run pytest-llm` passes
- [ ] `meridian --fork c1 --dry-run` shows a fork launch plan
- [ ] `meridian --fork c1 --continue c1` errors: "Cannot combine --fork with --continue"
- [ ] `meridian claude --fork c1 --dry-run` works (shortcut command)
- [ ] `meridian --fork c1 -m gpt --dry-run` works (model override allowed)
