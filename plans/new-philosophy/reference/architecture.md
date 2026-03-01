# Meridian-Channel Architecture

**Status:** Post-refactor target state (2026-02-28) — describes the intended final state, not current code

## Core Model

Meridian-Channel is a coordination layer with **files as the only authority**.

- No SQLite anywhere (including skill registry)
- **Everything is an agent** — no `supervisor` concept. The primary agent is launched by `meridian start`, but it's just an agent. Any agent can spawn child agents via `run spawn`. Codebase uses `primary` (first agent) and `harness` (process) — never `supervisor`.
- No single-harness-per-space assumption
- No `active-spaces/` directory
- Runtime state lives under `.meridian/.spaces/<space-id>/`
- Agent work product lives in `fs/` and is the only committed space content
- Space status: `active` or `closed` only (no intermediate states)
- `space.json` writes use atomic pattern (`.tmp` → `os.rename()`) with per-space `space.lock`
- flock-based locking assumes local filesystem (not NFS)

## Storage Layout

```text
.meridian/
├── agents/                    # User-authored agent profiles
├── skills/                    # User-authored skills
├── config.toml                # User-authored settings
├── .gitignore                 # Auto-created; ignores runtime, keeps fs/
└── .spaces/
    ├── .lock                  # Global lock for space ID generation
    └── <space-id>/
        ├── space.lock         # Per-space lock for space.json read-modify-write
        ├── space.json         # Space metadata (runtime state)
        ├── runs.lock          # Lock for runs.jsonl appends + run ID generation
        ├── runs.jsonl         # Append-only run events
        ├── sessions.lock      # Lock for sessions.jsonl appends
        ├── sessions.jsonl     # Append-only session events
        ├── sessions/
        │   └── <session-id>.lock
        ├── runs/
        │   └── <run-id>/      # Run artifacts (never auto-cleaned)
        └── fs/                # Agent working directory (committed)
```

## space.json

Space metadata is machine-managed JSON at `.meridian/.spaces/<id>/space.json`.

```json
{
  "schema_version": 1,
  "id": "s3",
  "name": "feature-auth",
  "status": "active",
  "started_at": "2026-02-28T10:00:00Z",
  "finished_at": null
}
```

Notes:
- `space.md` is removed.
- There is no `supervisor` field.
- Removed from MVP: `description`, `labels`, `pinned_files`, `last_activity_at`.
- `schema_version` for V2 forward compatibility.
- Status: `active` (finished_at is null) or `closed` (finished_at is set).

## Run Tracking

`runs.jsonl` stores start/finalize events (append-only). All events include `"v": 1` for schema versioning. Truncated trailing lines from crash are silently skipped by readers (self-healing).

```json
{"v":1,"event":"start","id":"r1","session_id":"c1","model":"gpt-5.3-codex","agent":"coder","harness":"codex","harness_session_id":"<codex conversation id>","status":"running","started_at":"2026-02-28T10:00:00Z","prompt":"..."}
{"v":1,"event":"finalize","id":"r1","status":"succeeded","exit_code":0,"duration_secs":128,"total_cost_usd":0.042,"input_tokens":4200,"output_tokens":1800,"finished_at":"2026-02-28T10:02:08Z"}
{"v":1,"event":"finalize","id":"r2","status":"failed","exit_code":1,"error":"Token limit exceeded","duration_secs":45,"finished_at":"2026-02-28T10:02:53Z"}
```

Run artifacts live at `.meridian/.spaces/<space-id>/runs/<run-id>/` and **are never auto-cleaned**.

## Session Tracking

A space can have multiple concurrent harness sessions.

- Session events append to `sessions.jsonl` (functional state — maps chat IDs to harness session IDs for `meridian start --continue` and `run continue`, and stores continuation defaults in `harness`, `model`, `params`)
- All `sessions.jsonl` appends hold `flock` on `sessions.lock` in the space directory
- Each live harness holds `flock` on `sessions/<session-id>.lock`
- Liveness: lock blocked = alive, lock acquirable = dead
- Authority chain: flock liveness is ground truth → `sessions.jsonl` is session-to-harness mapping → `space.json.status` is derived/cached
- `space.json.status` can become stale if harness crashes — `doctor` reconciles
- `MERIDIAN_SESSION_ID` env var set by `meridian start` for the current chat alias (`c1`, `c2`, ...)
- `harness_session_id` stored in session start events and run start events — enables `run continue` and `meridian start --continue` (with optional `--space` disambiguation)
- `--continue` accepts chat aliases (`cN`) and raw harness session IDs; without `--space`, lookup searches across spaces
- Ambiguous alias lookup errors with `[AMBIGUOUS_SESSION]`; harness switches during continuation error with `[HARNESS_MISMATCH]`
- Continuation is harness-locked, but model changes within the same harness are allowed
- Session start events record original passthrough `params`; explicit continuation flags are additive/overriding, with unsupported flags downgraded to `[UNSUPPORTED_FLAG]` warnings
- Truncated trailing lines in sessions.jsonl silently skipped by readers (self-healing)
- Cleanup:
  - Opportunistic on `meridian start`
  - Full cleanup on `space close`
  - Manual sweep via `meridian doctor` (auto-repairs, reports what it did)
- `doctor` scope: stale session locks, orphan runs, stale `space.json` status, and missing/corrupt `space.json` detection (report + skip, no recreate)

## Security Model

Cooperative trust model for MVP:
- Agents are assumed to be same-user, local trust. No hard sandbox, no capability tokens, no per-space OS isolation.
- `MERIDIAN_SPACE_ID` is context, not authorization — agents can set it to any value.
- Known limitation: documented explicitly. V2 may add per-space sandboxing if adversarial model is needed.

## Git Behavior

Meridian auto-creates `.meridian/.gitignore` on first space creation:

```gitignore
.spaces/**
!.spaces/*/
!.spaces/*/fs/
!.spaces/*/fs/**
```

This means:
- Runtime metadata/logs/artifacts are ignored
- `fs/` content is committed

## Environment Contract

- `MERIDIAN_SPACE_ID`: required context for space-scoped operations
- `MERIDIAN_SPACE_FS`: primary path for agents with shell access
- `MERIDIAN_SESSION_ID`: current chat alias (set by `meridian start`, used by `run continue`)
- `MERIDIAN_HARNESS_COMMAND`: resolved harness CLI command (for example `claude` or `codex`), set by `meridian start`

## Config Conventions

- Layered merge (later wins): built-in defaults, then base `config.toml`, then override config from `--config` or `MERIDIAN_CONFIG` when provided.
- `meridian init` writes a self-documenting `config.toml` template with all options present but commented out, including defaults.
- `[start].auto_resume` controls `meridian start` default behavior: `true` auto-resolves last active space (or creates one if none), `false` starts a new space unless `--space` is provided. Explicit `--continue` still resolves a continuation target.

## Command Surface

### Context-aware CLI

`meridian` detects `MERIDIAN_SPACE_ID` to switch help output:

- **No space ID** → human mode: all commands (start, space list/show/close, config, init, serve, completion). Output defaults to human-readable text.
- **Space ID set** → agent mode: only agent-relevant commands (run, skills, models, doctor). Output defaults to JSON.
- Hidden `--human` flag forces full help (documented in human help only, never shown to agents)

### MCP surface = agent commands only

`meridian serve` registers only agent-mode commands as MCP tools (11 tools). `start`, `space list/show/close` are never MCP tools — they launch/manage harness processes, which is meaningless over MCP.

### Deleted commands

- `migrate run` — no SQLite
- `export space` — no SQLite export; fs/ is committed
- `skills reindex` — no index; directory scan every time
- `space read/write/files` — cut; agents use shell or harness file tools under `$MERIDIAN_SPACE_FS/`
- `fs read/write/ls` — cut from MVP
- `space start/resume` — replaced by `meridian start` with `--new`/`--space`/`--continue`
- `run retry` — cut
- `context list/pin/unpin` — cut from MVP

### Renamed commands

- `diag repair` → `doctor` (canonical name, not a shortcut)

See `reference/cli-spec.md` for the complete CLI specification.
