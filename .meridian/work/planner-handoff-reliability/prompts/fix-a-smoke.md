# Smoke Test — Fix A: uniform prompt-size validation

Verify that the newly-added `validate_prompt_size()` check (see `src/meridian/lib/harness/connections/base.py`) correctly fails loudly on over-limit prompts and passes through for the previously-failing case. The failure case we're specifically protecting against is the real planner handoff that was truncating at 50 KiB in Codex (see `.meridian/work/planner-handoff-reliability/requirements.md`).

## Scenarios

### 1. Codex — previously-truncated prompt now succeeds

Build a prompt of ~60 KiB (above the old 50 KiB Codex ceiling, well under the new 10 MiB cap). Spawn a Codex-backed agent with that prompt. Verify:

- Spawn reaches `succeeded` or at least `running`-then-terminated-normally.
- No `warning/promptTruncated` event is emitted.
- `prompt_length` in `params.json` matches the full prompt byte count (no silent truncation).

A minimal approach: use `--agent meridian-subagent` or any no-op agent, and pad the prompt body with filler text (e.g. `"padding-" * N`) to reach ~60 KiB. The agent just needs to run — you're testing the adapter path, not the agent behavior.

Invoke from the meridian-cli repo root with `uv run meridian spawn ...`, since the fix is in source. DO NOT use the installed `meridian` binary — it hasn't been rebuilt with the fix.

### 2. Codex — over-limit prompt fails loudly

Build a prompt of ~11 MiB (just over the new 10 MiB cap). Spawn same as above. Verify:

- Spawn status goes to `failed`.
- `stderr.log` or the terminal report contains a reference to `PromptTooLargeError` with actual and max byte counts.
- The error surfaces before any network I/O to the Codex server (adapter should refuse to connect).

### 3. Claude — under-limit sanity check (optional but recommended)

Confirm the new validation call on the Claude path doesn't break the happy case. Small spawn with a normal prompt via Claude; verify it reaches `running` and completes normally.

### 4. OpenCode — under-limit sanity check (optional but recommended)

Same as #3 but via OpenCode, if your environment has OpenCode reachable. If not, skip and note in the report.

## Environment notes

- Must use `uv run meridian ...` so the in-repo source is exercised (the installed binary predates the fix).
- Do not touch `.meridian/spawns/` or any spawn artifacts — meridian owns those.
- Clean up any work items you create solely for smoke testing when done (or name them clearly so we can delete them later).

## Report

1. Which scenarios ran (1, 2, 3, 4).
2. For each: spawn id, observed status, relevant log lines (especially the error message shape for scenario 2).
3. Judgment: does the new validation behave correctly end-to-end? Any surprises?
4. If any scenario was skipped, say why (e.g. "OpenCode not reachable in this environment").

Do not edit source files. Report-only.
