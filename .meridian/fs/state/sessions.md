# Session Store

Source: `src/meridian/lib/state/session_store.py`

## What Sessions Track

A "session" in Meridian is a running harness instance (Claude Code, Codex, OpenCode) — typically a primary interactive launch. Sessions are distinct from spawns: spawns track individual task executions; sessions track the ongoing agent conversation context.

Meridian session IDs (`chat_id`) are `c1`, `c2`, `c3`, ... — allocated from a monotonic counter file (`.meridian/session-id-counter`). Harness session IDs are the native IDs from the underlying harness (e.g., a Claude UUID or Codex rollout UUID).

## Event Model

Events in `.meridian/sessions.jsonl`:

**`start`** — written when a session begins. Fields:
- `chat_id`, `harness`, `harness_session_id`, `execution_cwd`
- `model`, `agent`, `agent_path`, `skills`, `skill_paths`, `params`
- `session_instance_id` — generation token (random UUID per session start)
- `started_at`, `forked_from_chat_id`

**`stop`** — written when session ends. Fields: `chat_id`, `session_instance_id`, `stopped_at`.

**`update`** — non-terminal state change. Fields: `chat_id`, `harness_session_id`, `session_instance_id`, `active_work_id`.

`SessionRecord` is the projection: derived by replaying all events for a `chat_id`. The `harness_session_ids` tuple accumulates all harness IDs seen across updates (for tracking sessions that got new harness IDs during continuation).

## ID Allocation

`next_session_id()` reads the counter file atomically, increments, and writes back. The counter is seeded from the count of existing `start` events in `sessions.jsonl` if the counter file doesn't exist (upgrade path).

## Locking and Leases

Sessions hold two artifacts while active:

**Lock file** (`.meridian/sessions/<chat_id>.lock`): `fcntl.flock(LOCK_EX)` held for the session's lifetime. Any new process trying to acquire the same lock will block or detect contention.

**Lease file** (`.meridian/sessions/<chat_id>.lease.json`): Written atomically alongside the lock. Contains:
- `pid` — the process holding the session
- `generation` — the `session_instance_id` UUID, changes each time the session starts

The lease enables stale session detection without needing to check if the lock file's PID is still alive: if the lease PID is dead or the generation doesn't match what the lock holder recorded, the session is stale.

`start_session()`: writes `start` event → acquires persistent lock → writes lease file.
`stop_session()`: writes `stop` event → releases lock → removes lease file.

## Stale Session Cleanup

`clean_stale_sessions()` (called by `doctor`):
1. Reads all sessions that have no `stop` event (i.e., no `stopped_at`)
2. For each, checks if the lease file PID is alive and generation matches
3. If stale: writes a `stop` event with current timestamp, removes lock/lease files

`doctor --repair-orphans` also triggers orphan spawn repair at depth=0.

## Session Reference Resolution

`resolve_session_ref()` resolves several ref formats to a `SessionRecord`:
- Meridian chat ID: `c1`, `c2`, etc.
- Harness session ID: native UUID or opaque string (searched across all records)
- Spawn ID: `p1`, `p2`, etc. — resolved via the spawn's `chat_id`
- Untracked: if no match found, delegates to each harness's `owns_untracked_session()` to detect sessions not recorded in Meridian's own store

## Session Log (`ops/session_log.py`)

Reads harness-specific session/conversation files (e.g., Claude's JSONL transcript files in `~/.claude/projects/`). Compaction-aware:
- `-c 0` = latest compaction segment, `-c 1` = previous, etc.
- `-n <N>` = last N messages, `--offset` for paging
- Reports whether earlier/later segments exist

## Session Search (`ops/session_search.py`)

Scans all compaction segments for a session, highlights matches, emits navigation commands pointing to surrounding context segments.

## Work Attachment

`active_work_id` in session update events tracks which work item the session is currently attached to. Updated via `update_session()` when work context changes.
