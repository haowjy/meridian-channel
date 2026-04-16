# Planner Handoff Reliability

## Problem

Two bugs converged to make the planner handoff in mars-agents (spawns p47/p48/p49) fail in a way that looked like two independent issues but was really one mechanism failure + one orchestrator prompt failure.

### Evidence

- **p48** (first planner run): prompt was 59,546 bytes. Codex adapter silently truncated to 51,200 bytes (its hardcoded `_MAX_INITIAL_PROMPT_BYTES = 50 * 1024` in `src/meridian/lib/harness/connections/codex_ws.py:48`). The dropped tail included the concrete task contract, so the planner reported "No concrete task was included beyond loading the instructions."
- **p49** (retry): identical 59,546-byte prompt, identical truncation. The wrapper misdiagnosed p48 as a stdin-pipe failure and switched to `--prompt-file`, but truncation is downstream of prompt ingestion — same byte boundary, same failure.
- **p47** (wrapper impl-orchestrator): monitored the planner spawn via background/notification mode and ended its turn instead of calling `meridian spawn wait`. Its report.md reads only: "Waiting for planner spawn to complete."

### Root causes

1. **Silent truncation with a pinched ceiling.** Codex adapter has a 50 KiB hardcoded initial-prompt cap, silently truncates over-limit prompts, emits a warning event, and proceeds with the mutilated prompt. Claude and OpenCode adapters have no analogous ceiling. The limits are inconsistent across harnesses and the failure mode is silent.
2. **Spawn-wait discipline missing from the mental model.** Background spawning gives a completion notification later, but agents treat that as a handoff and finalize their turn before the child terminates. The `meridian-spawn` skill does not explicitly forbid this pattern.

## Success criteria

### Fix A — uniform fail-loud prompt validation (meridian-cli)

1. Shared `MAX_INITIAL_PROMPT_BYTES` constant and `PromptTooLargeError` exception live in `src/meridian/lib/harness/connections/base.py`.
2. A shared helper validates the prompt size and all three adapters (`claude_ws.py`, `codex_ws.py`, `opencode_http.py`) call it during connection start.
3. `codex_ws.py`'s silent truncation (`_truncate_utf8`, the `warning/promptTruncated` event emission, the local `_MAX_INITIAL_PROMPT_BYTES` constant) is removed.
4. Over-limit prompts cause spawn to fail with a clear error naming actual vs. allowed bytes.
5. Under-limit prompts pass through unchanged on all three adapters.
6. `pyright` clean, `ruff` clean, unit tests pass.
7. Smoke test: Codex spawn with a ~60 KiB prompt succeeds (previously truncated); Codex spawn with an 11 MiB prompt fails loudly with `PromptTooLargeError`.

**Chosen ceiling: 10 MiB (`10 * 1024 * 1024`).** Generous enough that no legitimate planner/design bundle hits it (~170× headroom over the 60 KiB failure case) and small enough to catch runaway prompts before they stress the transport.

### Fix B — wait-before-finalize principle in `meridian-spawn` skill

1. `~/gitrepos/prompts/meridian-base/skills/meridian-spawn/SKILL.md` gains a new H2 section "Wait Before You Finalize" placed right after Core Loop, before Spawning.
2. The existing Core Loop sentence that reads "The preferred pattern is to spawn these in the background so you get a completion notification later" is revised to stop implying that background spawning is a handoff.
3. The new section explicitly names the "report body = 'waiting for X to complete'" pattern as a bug and covers the background-mode case.
4. The edit lands in the `meridian-base` source repo. Propagation to consuming repos happens via `meridian mars sync` (tracked but not executed in this work item).

## Constraints

- No backwards compatibility needed (per CLAUDE.md).
- Fix B lives in a sibling checkout (`~/gitrepos/prompts/meridian-base/`), not in this repo. Don't edit `.agents/` directly — edit the source.
- Don't touch the impl-orchestrator profile in this work item. The `orchestrator-profile-hardening` work item covers profile-level reinforcement.
