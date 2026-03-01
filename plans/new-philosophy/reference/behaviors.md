# Meridian-Channel Behaviors

**Status:** Post-refactor target state (2026-02-28) — describes the intended final state, not current code

This document defines expected user-facing behavior after the files-as-authority refactor.

## Space Lifecycle

### `meridian start`

Default behavior (`[start].auto_resume = true`, default):
1. Resolve last active space if one exists; otherwise create a new space under `.meridian/.spaces/<space-id>/`.
2. If a space was auto-resolved, emit:
   `WARNING [SPACE_AUTO_RESUMED]: Resumed active space s3 ("feature-auth"). Next: use --new to start a fresh space.`
3. Ensure `.meridian/.gitignore` exists with the `.spaces/**` ignore exceptions for `fs/`.
4. If creating a space, create `space.lock`, `space.json` (`schema_version: 1`), `runs.lock`, `sessions.lock`, `sessions.jsonl`, `sessions/`, `runs/`, and `fs/`.
5. Run opportunistic stale-session cleanup (lock/liveness sweep).
6. Start harness session and append session `start` event (including `harness_session_id`, `harness`, `model`, `params`) to `sessions.jsonl` under `flock` on `sessions.lock`.
7. Acquire `flock` on `sessions/<session-id>.lock`.
8. Set `MERIDIAN_SPACE_ID`, `MERIDIAN_SPACE_FS`, `MERIDIAN_SESSION_ID`, `MERIDIAN_HARNESS_COMMAND` in child env.
9. Launch conversation mode based on flags (new chat by default, continuation only with `--continue`).

Flag variants:
- `meridian start --new` forces creation of a new space and starts a new chat (overrides auto-resolve).
- `meridian start --space <space-id>` uses explicit space and starts a new chat.
- `meridian start --continue` auto-resolves last active space and continues its last chat.
- `meridian start --continue <chat-id|harness-session-id>` resolves across spaces and continues the target chat/session.
- `meridian start --space <space-id> --continue` continues last chat in explicit space (optional disambiguation).
- `meridian start --space <space-id> --continue <chat-id|harness-session-id>` resolves only within explicit space.

Continuation behavior:
1. Resolve continuation target:
   - no value: last chat in last active space
   - chat alias (`cN`): search across spaces unless `--space` is provided
   - raw harness session ID: search across spaces unless `--space` is provided
2. If a chat alias matches multiple spaces, error: `ERROR [AMBIGUOUS_SESSION]: Chat c2 exists in multiple spaces. Next: use --space to disambiguate.`
3. Enforce harness lock from the original session record (`harness`):
   - if `-m` implies a different harness, error: `ERROR [HARNESS_MISMATCH]: Session c2 was started with Claude. Cannot continue with a Codex model. Next: pick a model on Claude or omit -m.`
   - model changes within the same harness are allowed
4. Merge passthrough flags: original `params` are defaults; explicit flags override/add.
5. If a passthrough flag is unsupported by the resolved harness, warn and ignore: `WARNING [UNSUPPORTED_FLAG]: --append-system-prompt is not supported by Codex. Next: remove this flag or switch to a harness that supports it. Flag ignored.`
6. Pass resolved `harness_session_id` through harness-native continuation flag.
7. Append new session `start` event and hold liveness lock for the new process.

Notes:
- There is no `active-spaces/` marker directory.
- There is no supervisor field/role.
- `runs.jsonl` created on first `run spawn`, not on space creation.

### `meridian space close <space-id>`

Expected behavior:
1. Mark space lifecycle state in `space.json` (set `finished_at`, status becomes `closed`)
2. Stop/cleanup all tracked sessions for that space
3. Append session `stop` events where needed under `flock` on `sessions.lock`
4. Remove stale lock files

No automatic git commit is implied by close.

## Run Lifecycle

Run metadata is append-only JSONL in `.meridian/.spaces/<space-id>/runs.jsonl`.

- `start` event written when run begins
- `finalize` event written when run ends
- Run artifacts are written under `.meridian/.spaces/<space-id>/runs/<run-id>/`
- Run artifacts are never auto-cleaned

### Space context requirement

All space-scoped commands require explicit space context:
- `--space <id>` on the command, or
- `MERIDIAN_SPACE_ID` in environment

**Exception:** `meridian run spawn` auto-creates a space if none is set, warns with the ID, and proceeds. All other commands (`run continue`, `run list`, `skills list`, etc.) error without space context.

## Session Tracking Semantics

A space may have multiple concurrent harness sessions. `sessions.jsonl` is functional state (not just audit trail) — it maps chat aliases (`c1`, `c2`, ...) to harness session IDs and stores continuation defaults (`harness`, `model`, `params`) for `meridian start --continue` and `run continue`.

State model:
- Log: `.meridian/.spaces/<space-id>/sessions.jsonl` (includes `harness_session_id`, `harness`, `model`, `params`)
- Append lock: `.meridian/.spaces/<space-id>/sessions.lock` (shared lock for all `sessions.jsonl` appends)
- Liveness lock: `.meridian/.spaces/<space-id>/sessions/<session-id>.lock`
- Env var: `MERIDIAN_SESSION_ID` (set by `meridian start` for the current chat alias, for example `c2`)

Liveness rule:
- lock blocked: session is alive
- lock acquirable: session is stale/dead

Cleanup behavior:
- Opportunistic on `meridian start`
- Full cleanup on `space close`
- Manual sweep available via `meridian doctor` (stale session locks, orphan runs, stale status, missing/corrupt `space.json` report+skip)

JSONL self-healing: truncated trailing lines (from crash mid-append) are silently skipped by readers. Only mid-file corruption produces a warning.

## Environment Variables

Primary environment contract:

```bash
MERIDIAN_SPACE_ID=<space-id>
MERIDIAN_SPACE_FS=<repo>/.meridian/.spaces/<space-id>/fs
MERIDIAN_SESSION_ID=<chat-id>   # Current chat alias (c1, c2...), set by meridian start
MERIDIAN_HARNESS_COMMAND=<command> # Resolved harness CLI command (e.g. claude, codex), set by meridian start
```

Notes:
- `MERIDIAN_SPACE_FS` is the canonical path for agent file operations (`$MERIDIAN_SPACE_FS/` with shell/harness tools).
- `MERIDIAN_SESSION_ID` is used by `run continue` (no args) to find the last run from the current chat.

## Configuration Behavior

Config resolution is layered (later layers win):
1. Built-in defaults (hardcoded)
2. Base config (`config.toml`)
3. Override config from `--config` or `MERIDIAN_CONFIG` when provided

`meridian init` generates `config.toml` with every option present but commented out, showing defaults. Users uncomment only the options they want to override.

`meridian start` auto-resume behavior is controlled by `[start].auto_resume`:
- `true` (default): `meridian start` auto-resolves active space (or creates one if none active)
- `false`: plain `meridian start` creates a new space unless `--space` is provided; explicit `--continue` still resolves a continuation target

## Storage/Path Conventions

Use dot-prefixed runtime path:

- `.meridian/.spaces/<space-id>/...`

Do not use legacy forms:
- `.meridian/<space-id>/...`
- `.meridian/spaces/<space-id>/...`

## Context-Aware CLI

`meridian` serves two audiences from a single binary:

- **Human mode** (no `MERIDIAN_SPACE_ID`): Shows all commands including start, space list/show/close, config, init, serve, completion. Output defaults to human-readable text.
- **Agent mode** (`MERIDIAN_SPACE_ID` set): Shows only agent-relevant commands — run, skills, models, doctor. Output defaults to JSON for programmatic piping.
- Hidden `--human` flag forces full help (not shown in agent-mode help, documented in human help only).

### Auto-create space (only on `run spawn`)

If an agent runs `meridian run spawn` without `MERIDIAN_SPACE_ID`:
1. Auto-create a space
2. Warn: `"WARNING [SPACE_AUTO_CREATED]: No MERIDIAN_SPACE_ID set. Created space s5. Next: set MERIDIAN_SPACE_ID=s5 for subsequent commands."`
3. Proceed with the run

All other commands error without space context. Only `run spawn` auto-creates.

### MCP surface

`meridian serve` registers **only agent-mode commands** as MCP tools. Space launcher commands are never MCP tools.

`doctor` is the canonical command name (not a shortcut to `diag repair`).

All agent-facing errors follow `[CODE] + cause + next action` format.

See `reference/cli-spec.md` for the complete command surface specification.

## Removed Commands

Deleted from CLI surface:
- `migrate run` — no SQLite
- `export space` — no SQLite export; fs/ is committed
- `skills reindex` — no index; directory scan every time
- `space read/write/files` — cut (agents use `$MERIDIAN_SPACE_FS/` directly)
- `fs read/write/ls` — cut (agents use `$MERIDIAN_SPACE_FS/` directly)
- `space start/resume` — replaced by `meridian start` with `--new`/`--space`/`--continue`
- `run retry` — cut from MVP
- `context list` — cut from MVP (agent has `MERIDIAN_SPACE_ID` from env)
- `context pin/unpin` — cut from MVP
