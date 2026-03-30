# Phase Fork 3: Harness Adapters — Claude Code + OpenCode Fork Flags

## Scope

Ensure Claude Code and OpenCode adapters correctly handle `SessionMode.FORK` via the existing CLI flag mechanism. Both adapters already have partial wiring (`--fork-session` for Claude, `--fork` for OpenCode). This phase verifies and completes the wiring so the adapters correctly produce fork commands when `continue_fork=True`.

## Intent

After this phase, `build_command()` on Claude and OpenCode adapters correctly appends fork flags when `SpawnParams.continue_fork=True`. Also update `seed_session()` and `filter_launch_content()` to handle fork mode correctly (new session behavior with existing conversation).

## Files to Modify

- **`src/meridian/lib/harness/claude.py`** — Verify `build_command()` (line ~228-256):
  - Already appends `--fork-session` when `continue_fork=True` ✓
  - Update `seed_session()`: when fork mode, `is_resume=False` (new meridian session) but `harness_session_id` is set. Current logic checks `is_resume` — ensure fork case produces correct `SessionSeed`.
  - Update `filter_launch_content()`: fork is NOT a resume — full content (skills, bootstrap) should be included. Current logic skips content on resume. Fork needs the opposite.

- **`src/meridian/lib/harness/opencode.py`** — Same updates:
  - Already appends `--fork` when `continue_fork=True` ✓
  - Update `seed_session()` for fork mode.
  - Update `filter_launch_content()` for fork mode.

- **`src/meridian/lib/harness/adapter.py`** — If `seed_session()` or `filter_launch_content()` signatures need a `continue_fork` parameter, update the `SubprocessHarness` protocol and `SpawnParams`.

## Dependencies

- **Requires**: Prep 5 (validation in place). Independent of Fork 1 and Fork 4.
- **Produces**: Correct adapter behavior for fork. Fork 5 relies on adapters handling fork correctly.

## Interface Contract

### Claude Code fork command:
```bash
claude --resume <harness_session_id> --fork-session
# Plus all normal flags (model, prompt, etc.)
```

### OpenCode fork command:
```bash
opencode run "prompt" --session <harness_session_id> --fork
# Plus all normal flags
```

### seed_session behavior for fork:
```python
def seed_session(self, *, is_resume: bool, harness_session_id: str, ...) -> SessionSeed:
    # For fork: is_resume=False but harness_session_id is set
    # Return: SessionSeed with the source session_id (for build_command)
    # but no resume-specific session_args
```

### filter_launch_content behavior for fork:
```python
def filter_launch_content(self, *, prompt, skill_injection, is_resume, harness_session_id) -> PromptPolicy:
    # For fork: is_resume=False → include full content (skills, bootstrap)
    # The fork gets a new session from meridian's perspective, needs all context
```

Note: The `is_resume` parameter determines content filtering. For fork, the caller (plan.py) should pass `is_resume=False` since fork is a new meridian session. The adapter doesn't need to know about fork mode for content filtering — it just sees "not a resume, include everything."

## Patterns to Follow

- See existing `build_command()` in `claude.py` (lines 228-256) and `opencode.py` (lines 186-203).
- See `seed_session()` implementations for how session IDs are seeded.
- See `filter_launch_content()` for content filtering logic.

## Constraints

- Do NOT modify codex.py — that's Fork 4.
- Do NOT modify the launch pipeline (plan.py, process.py) — that's Fork 5.
- Changes should be minimal since both adapters already have fork flag wiring. The main work is ensuring `seed_session()` and `filter_launch_content()` produce correct results for the fork case.
- If `seed_session()` needs to distinguish fork from fresh, consider whether the existing `is_resume` parameter is sufficient or if `continue_fork` should be added to the signature.

## Verification Criteria

- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes with 0 errors
- [ ] `uv run pytest-llm` passes
- [ ] Claude adapter produces `claude --resume UUID --fork-session` when `continue_fork=True`
- [ ] OpenCode adapter produces `opencode run "prompt" --session UUID --fork` when `continue_fork=True`
- [ ] `filter_launch_content()` returns full content (not suppressed) for fork mode
