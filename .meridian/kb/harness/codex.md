# Codex Harness Adapter

Source: `src/meridian/lib/harness/codex.py`

## Command Shape

Non-interactive spawn:
```
codex exec --json [--model <model>] [-c model_reasoning_effort="<effort>"] \
  [permission flags...] "<prompt>"  # positional
```

Resume:
```
codex exec resume <session_id> "<prompt>"
```

Interactive (primary launch):
```
codex [--model <model>] ...
```

Note: Codex uses `codex exec` for non-interactive runs and positional prompt mode. Unlike Claude, prompt is a positional argument, not stdin.

## Capabilities

`supports_stream_events`, `supports_session_resume`, `supports_session_fork`, `supports_primary_launch`, `supports_stdin_prompt`, `supports_native_skills` all enabled. No native agents, no programmatic tools.

## Primary Launch Context

Codex has no Meridian-managed side channel equivalent to Claude's `--append-system-prompt` for primary launch startup context. Launch-layer injected content such as the current agent profile body, skill content, and the startup `# Meridian Agents` inventory is flattened into the inline primary prompt body for fresh and forked sessions.

Resume sessions keep the existing behavior and do not receive a newly composed startup inventory block.

## Session Handling

**Critical constraint:** Codex always generates its own session UUID at launch — callers cannot inject a session ID. Meridian must discover the session ID post-launch by scanning `~/.codex/sessions/`.

**Session storage:** `~/.codex/sessions/YYYY/MM/DD/rollout-<UUID>.jsonl` (or `.jsonl.zst` compressed). A SQLite metadata index lives alongside for fast listing. The UUID is embedded *inside* the JSONL file (in the `session_meta` event), not just in the filename — renaming the file doesn't change the internal ID.

**Resume:** `codex exec resume <SESSION_ID> "<prompt>"`. The Meridian adapter maps `continue_harness_session_id` to this form.

**Fork:** Meridian implements fork in-process via `fork_session()`:
1. Looks up the source rollout file by scanning for `rollout-*-<source_id>.jsonl`
2. Generates a new UUID4
3. Atomically copies the rollout file with `_copy_rollout_atomic()`, rewriting the `session_meta` first line to embed the new session ID
4. Fsyncs both the file and directory for crash safety
5. Updates the SQLite state database with the new thread's metadata

This is a Meridian-side implementation, not a call to `codex fork`. Reason: `codex fork` is interactive and has no non-interactive equivalent that returns a session ID programmatically.

## Session Detection (Primary Launch)

`detect_primary_session_id()` scans `~/.codex/sessions/**/*.jsonl` for files modified at or after the spawn start time. For each candidate, it reads the `session_meta` event to verify:
- `cwd` in the rollout matches the repo root
- At least one assistant message was written (not just an aborted turn)

Returns the session ID from the most recently modified matching file.

Session validation also excludes rollout files where `turn_aborted` was seen without any assistant message — those represent failed/aborted launches, not usable sessions.

## Rollout File Format

JSONL, one event per line. Key event types:
- `session_meta` (first line) — contains `{"payload": {"id": "<uuid>", "cwd": "...", ...}}`
- `response_item` — assistant messages, tool calls
- `event_msg` — turn lifecycle events (`turn_aborted`, etc.)

The session UUID in `session_meta.payload.id` is the canonical ID. Filename also embeds the UUID: `rollout-<timestamp>-<uuid>.jsonl`.

## Effort Mapping

Codex effort is set via `-c model_reasoning_effort="<value>"` config flag, not a dedicated `--effort` flag. The transform appends this config pair.

## Report Extraction

`extract_codex_report()` parses `output.jsonl` for the last assistant message content. If `report.md` is present, it takes precedence.

## Key Limitation for Meridian

Cannot inject session ID at launch — Codex always generates its own UUID. This means:
1. A fresh spawn cannot know its harness session ID until after `detect_primary_session_id()` runs
2. Fork is implemented by Meridian directly manipulating the rollout files rather than delegating to the Codex CLI
