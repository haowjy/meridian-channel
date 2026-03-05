# Harness Layer Cleanup — Important Tests

Tests identified during implementation of the 8-step harness refactoring.

## Step 1: Adapter Prompt/Resume Hooks

- **Per-adapter resume prompt suppression**: Each adapter's filter_launch_prompt() must return empty string on resume. Test with is_resume=True + harness_session_id set.
- **Codex "DO NOT ACT" guard**: filter_launch_prompt() must append guard text on fresh interactive, NOT on resume.
- **filter_skill_injection None on resume**: All adapters must return None when is_resume=True.
- **MERIDIAN_SPACE_PROMPT env var on resume**: Must be populated (not empty) even for Codex resume. Regression guard.
- **build_command() still works with full prompt**: After launch.py stops clearing prompt, each adapter's build_command() must handle non-empty prompt on resume correctly.

## Step 2: OutputSink

- **AgentSink stdout is exactly one JSON object**: No interleaved events, no text.
- **AgentSink stderr is empty**: No heartbeats, no errors, no status text.
- **TerminalSink respects format**: json/text/porcelain produce correct output.
- **error() does NOT raise SystemExit**: Caller controls flow.

## Step 3-4: Session Detection/Seeding

- **Claude seed_session_id() returns UUID**: Non-empty, valid format.
- **Codex detect_session_id() finds session**: With mock filesystem.
- **inject_session_passthrough() only for Claude**: Adds --session-id.

## Step 5-6: RuntimeContext

- **from_environment() reads all MERIDIAN_* vars**: Correct parsing.
- **child_context() increments depth**: Parent spawn_id becomes parent_spawn_id.
- **to_env_vars() round-trips**: from_environment(to_env_vars()) preserves values.

## Step 7: launch.py Decomposition

- **launch_primary() still works end-to-end**: Integration test with dry_run=True.
- **No import cycles**: All 4 modules import cleanly.

## Step 8: Explicit Sink Threading

- **Sink reaches all output points**: No orphaned print() calls remain.
