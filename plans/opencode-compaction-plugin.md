# OpenCode Compaction Plugin + Session Recording + Run Output Fix

**Status:** draft

## Problem

Four related gaps:

1. **Naming confusion.** `session_id` is overloaded — Meridian's internal chat counter (`c0`, `c1`) vs harness session IDs. `continue_session_id` is ambiguous about which concept it refers to.

2. **Session recording is dead code.** `session_store.start_session()` exists with full start/stop/cleanup machinery but is never called. No record of what params a session was launched with.

3. **`meridian run spawn` output is broken.** Foreground runs return nothing useful to stdout (report is extracted to file but never printed). Background runs dump the entire composed command JSON (~100KB) to stdout. Compare with `run-agent.sh` which prints initial info to stderr and the report to stdout — the right pattern.

4. **OpenCode loses context on compaction.** Skills, agent body, and model guidance injected into the composed prompt get lost. Claude solves this with native agent passthrough; OpenCode has no equivalent.

## Design

### Phase 0: Naming cleanup

Disambiguate the two "session ID" concepts across the codebase.

**Meridian chat counter** (`c0`, `c1`, ...):
- `MERIDIAN_SESSION_ID` → `MERIDIAN_CHAT_ID`
- `session_id` field → `chat_id` in `SessionRecord`, `RunRecord`, `start_session()`, `start_run()`, JSONL event keys
- `next_session_id()` → `next_chat_id()`
- `_resolve_session_id()` → `_resolve_chat_id()`

**Continuation harness session** (harness-specific session ID for resume):
- `continue_session_id` → `continue_harness_session_id` in `RunCreateInput`, `RunParams`, `_PreparedCreate`, `_PreparedCreateLike`, adapters, `_run_prepare.py`, `_run_execute.py`, `spawn.py`
- Background worker CLI flag `--continue-session-id` → `--continue-harness-session-id`
- `continue_harness` stays as-is

**Harness-extracted session IDs** (clarify, not rename to chat_id):
- `FinalizeExtraction.session_id` → `harness_session_id` (it's the harness session, not chat counter)
- `RunResult.session_id` → `harness_session_id` (same)

**Unchanged:**
- `harness_session_id` field in SessionRecord, RunRecord — already clear
- `session_store.py` module name, `start_session()`/`stop_session()` function names
- `SessionRecord` class name
- `continue_fork` — already clear

**Additional files to include:**
- `src/meridian/lib/state/__init__.py` — re-export rename
- `src/meridian/lib/extract/finalize.py` — `FinalizeExtraction.session_id` → `harness_session_id`
- `src/meridian/lib/harness/adapter.py` — `RunResult.session_id` if present

### Phase 1: Wire session recording (all harnesses)

**Session record as source of truth.** Every harness launch records a session with all resolved launch params. Capture everything Meridian already resolved at launch time — the plugin should never need to re-derive anything.

```jsonl
{"event":"start","chat_id":"c1","harness":"opencode","harness_session_id":"",
 "model":"gpt-5.3-codex",
 "agent":"coder","agent_path":"/repo/.claude/agents/coder.md",
 "skills":["run-agent","orchestrate"],
 "skill_paths":["/repo/.claude/skills/run-agent/SKILL.md","/repo/.agents/skills/orchestrate/SKILL.md"],
 "started_at":"2026-03-01T..."}
```

**Session record fields — persist all resolved state:**
- `agent: str | None` — agent profile name
- `agent_path: str | None` — absolute path to the agent profile file that was loaded
- `skills: tuple[str, ...]` — resolved skill names
- `skill_paths: tuple[str, ...]` — absolute paths to SKILL.md files that were loaded (same order as skills)
- `model: str` — resolved model ID
- `harness: str` — resolved harness ID
- `harness_session_id: str` — empty on fresh runs, populated after extraction

The plugin reads `agent_path` and `skill_paths` directly — no search logic, no config parsing, always matches what was actually loaded.

**New session_store functions:**
- `update_session_harness_id(space_dir, chat_id, harness_session_id)` — appends an `"update"` event to sessions.jsonl after harness session ID is extracted from stream output. `_records_by_session` replays it.

**Backward compat:** `_record_from_start_event()` defaults new fields to None/empty when absent (old events pre-Phase 1).

**Wiring:**

1. **Subagent runs** (`_run_execute.py`):
   - For **blocking** runs: call `start_session()` before spawning, `stop_session()` in finally block after finalization. Call `update_session_harness_id()` after `extract_session_id()`.
   - For **background** runs: wire start/stop in the **worker** process (`_execute_existing_run`), not the launcher. The launcher subprocess doesn't inherit the parent's lock FD (`close_fds=True`), so locking in the parent is wrong.

2. **Primary launches** (`launch.py`):
   - `execvp` path: call `start_session()` before exec. Lock FD is inherited by exec (same process image). Stop happens via `cleanup_stale_sessions()` on next CLI invocation.
   - `Popen` path: call `start_session()` before Popen, `stop_session()` in `finally` block (not after `wait()` — must fire on Ctrl-C).
   - Call `update_session_harness_id()` after harness session ID is available (for Popen path, after run finishes and extraction runs).
   - Add `MERIDIAN_STATE_ROOT` to `_build_space_env()` (already set for subagent runs in spawn.py, missing for primary launches).

3. **Continue/resume param inheritance:**
   - When `continue_harness_session_id` is set, look up session record by harness_session_id
   - Use `resolve_session_ref()` — fix to return **newest** matching record (not oldest)
   - Inherit agent, skills, model, skill_paths, agent_path unless user explicitly overrides
   - Write new session start event with resolved params

4. **Stale session cleanup:**
   - Add `cleanup_stale_sessions()` call during normal CLI startup (alongside existing `cleanup_orphaned_locks()`), outside subagent mode

### Phase 2: Fix `meridian run spawn` output

Rename `--include-report` to `--report` on `run show` and `run wait`.

Match `run-agent.sh` behavior: initial info to stderr, report to stdout.

**Foreground (blocking) runs:**
- After run completes and report is extracted, print the report content to stdout
- If no report, print the last assistant message (or a warning) to stderr
- Run metadata (run_id, model, harness, status, duration, exit_code) goes to stderr

**Background runs:**
- Print just the run ID to stdout (callers capture via `R1=$(meridian run spawn --background ...)`)
- Run metadata to stderr
- The current behavior dumps ~100KB of JSON including the full composed prompt — fix to only emit the run ID

**Implementation:**
- Modify `RunActionOutput.format_text()` for background: already returns just run_id (correct)
- Modify the foreground spawn path in `run.py` to read the extracted report from the artifact store and print to stdout
- The JSON output mode (`--format json`) continues to return full structured JSON (no change)

### Phase 3: OpenCode compaction plugin

Plugin reads session record to know what to reinject on compaction.

**`.opencode/plugins/meridian.ts`** (~50-60 lines):
- `experimental.session.compacting` hook
- Gets `input.sessionID` (OpenCode's session ID) from the hook
- Reads `MERIDIAN_STATE_ROOT` and `MERIDIAN_SPACE_ID` from `process.env`
- Parses `sessions.jsonl`, finds record where `harness_session_id == input.sessionID`
- Reads `agent_path` and `skill_paths` from the matching record
- Reads each file directly (absolute paths, no search logic needed)
- Pushes skill content and agent profile body into `output.context`
- No-op when env vars are unset or no matching session (non-Meridian sessions)
- Handles truncated trailing JSONL line gracefully (ignore malformed last line, same as session_store)

Note: compaction only matters on continued sessions. By the time a session is continued, the harness_session_id is always known from the previous run's extraction.

## Scope

### Files

**Phase 0 (rename):**
- `src/meridian/lib/state/run_store.py` — `session_id` → `chat_id` in RunRecord + events
- `src/meridian/lib/state/id_gen.py` — `next_session_id()` → `next_chat_id()`
- `src/meridian/lib/state/__init__.py` — re-export rename
- `src/meridian/lib/space/session_store.py` — `session_id` → `chat_id` in SessionRecord + events
- `src/meridian/lib/ops/_run_execute.py` — env var rename + `continue_session_id` → `continue_harness_session_id`
- `src/meridian/lib/ops/_run_prepare.py` — `continue_session_id` → `continue_harness_session_id`
- `src/meridian/lib/ops/_run_models.py` — field rename in RunCreateInput
- `src/meridian/lib/exec/spawn.py` — env var + param rename
- `src/meridian/lib/harness/adapter.py` — field rename in RunParams + RunResult
- `src/meridian/lib/harness/claude.py` — field reference update
- `src/meridian/lib/harness/opencode.py` — field reference update
- `src/meridian/lib/harness/codex.py` — field reference update
- `src/meridian/lib/harness/direct.py` — field reference update
- `src/meridian/lib/harness/_strategies.py` — strategy key update
- `src/meridian/lib/harness/_common.py` — if applicable
- `src/meridian/lib/extract/finalize.py` — `session_id` → `harness_session_id`
- `src/meridian/lib/ops/run.py` — field references
- `src/meridian/lib/ops/diag.py` — if applicable
- `tests/` — update all assertions

**Phase 1 (session recording):**
- `src/meridian/lib/space/session_store.py` — Add agent/skills/paths fields, `update_session_harness_id()`, fix `resolve_session_ref()` ordering
- `src/meridian/lib/ops/_run_execute.py` — Wire start/stop (blocking in execution path, background in worker)
- `src/meridian/lib/space/launch.py` — Wire start for primary (both execvp and Popen paths, stop in finally), add `MERIDIAN_STATE_ROOT` to env
- `src/meridian/cli/main.py` — Add `cleanup_stale_sessions()` to startup
- `tests/` — Session recording tests

**Phase 2 (run output fix):**
- `src/meridian/lib/ops/run.py` — Foreground: print report to stdout after completion
- `src/meridian/lib/ops/_run_execute.py` — Background: return only run_id
- `src/meridian/lib/ops/_run_models.py` — May need output model adjustments
- `tests/` — Output format tests

**Phase 3 (plugin):**
- `.opencode/plugins/meridian.ts` — New plugin

## Phase ordering

**Phase 0 → Phase 1 → Phase 2 → Phase 3** (sequential)

- Phase 1 depends on Phase 0 (renamed fields)
- Phase 2 is independent of Phase 1 but sequenced after for clean commits
- Phase 3 depends on Phase 1 (reads agent/skills/paths from session records written by Phase 1)

## Edge cases

- **`execvp` primary path**: Lock FD inherited by exec. `cleanup_stale_sessions()` on next invocation stops the session.
- **Background run lock scope**: Start/stop wired in worker process, not launcher. Worker holds the lock for its lifetime.
- **Fresh run compaction**: No harness_session_id in record yet, plugin finds no match → no-op. Harmless — nothing worth reinjecting on first exchange.
- **sessions.jsonl doesn't exist**: Plugin no-ops gracefully.
- **Truncated JSONL tail**: Plugin ignores malformed last line (mirrors session_store behavior).
- **Concurrent async start_session() calls**: `_SESSION_LOCK_HANDLES` is module-level dict, no thread lock. Fine for single-threaded CLI; note if async concurrency grows.
- **Ctrl-C during Popen wait**: `stop_session()` in finally block ensures session is stopped.

## Non-goals

- Claude compaction (solved by native agent passthrough)
- Codex compaction (no plugin system)
- Storing the full composed prompt in session records
- Changing how skills are discovered/loaded from disk
