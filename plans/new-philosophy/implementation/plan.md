# Implementation Plan: Files-as-Authority Refactor

**Status:** done
**Date:** 2026-02-28
**Basis:** review/synthesis.md (3x gpt-5.3-codex + 1x claude-opus-4-6), then 3x codex alignment pass, then 4x codex + 1x opus cross-examination pass

---

## Scope

Single-phase refactor: replace all SQLite with file-based authority, delete all SQLite infrastructure (including skill_registry), clean up CLI surface. No backwards compatibility needed.

## Decisions

1. **No SQLite anywhere** — files are sole authority. No cache, no index. Directory scans + JSONL parsing at this scale (dozens of spaces, hundreds of runs) is milliseconds. Includes `skill_registry.py` (replace with filesystem scan).
2. **`MERIDIAN_SPACE_FS` env var** — primary path for agents. All file operations use `$MERIDIAN_SPACE_FS/` directly (shell tools, harness file tools, etc.). No meridian-provided `fs` commands.
3. **Prompt composition stays** — `--skills` becomes additive over agent profile defaults. Pipeline untouched.
4. **Runs in JSONL** — `.meridian/.spaces/<space-id>/runs.jsonl` (append-only). Run status is derived from the last event for a given run ID (start=running, finalize=terminal state). No separate status-update events.
5. **Spaces in JSON** — `.meridian/.spaces/<space-id>/space.json` (read/write in place). Machine-managed runtime state, not config — no markdown, no YAML. All writes use atomic pattern (write to `.tmp` → `os.rename()`). All read-modify-write operations hold per-space `space.lock`.
6. **Path convention** — `.meridian/.spaces/<id>/` (dot-prefix separates runtime state from user-authored content like `agents/`, `skills/`, `config.toml` — prevents future namespace collisions).
7. **One phase** — rip the bandaid.
8. **Everything is an agent** — no `supervisor` concept. The primary agent is launched by `meridian start`, but it's just an agent. Any agent can spawn child agents via `run spawn`. Codebase terminology uses `primary` (for the first agent launched) and `harness` (for the process running it) — never `supervisor`.
9. **Session tracking** — multiple concurrent harnesses per space. Each harness gets a flock in `sessions/<session-id>.lock`. Metadata in `sessions.jsonl` (functional state — maps chat IDs to harness session IDs and stores continuation defaults: `harness`, `model`, `params`). All `sessions.jsonl` appends are serialized with `flock` on `sessions.lock` in the space directory. Runs link to chats via `session_id` in start events. `MERIDIAN_SESSION_ID` env var is set by `meridian start` for the current chat.
10. **Session cleanup** — opportunistic on `meridian start` (scan stale locks), full on `space close`. `doctor` as manual sweep.
11. **Gitignore convention** — auto-create `.meridian/.gitignore` on first space creation. Gitignore everything in `.spaces/` except `*/fs/` (agent work product is committable). **Constraint:** repo root `.gitignore` must NOT contain `.meridian/` — parent ignores block nested carve-outs.
12. **Run artifacts** — accumulate in `runs/<run-id>/`, never cleaned up automatically. Agents grep over them directly. Primary agent copies important outputs to `fs/` for long-term keeping.
13. **Context-aware CLI** — `meridian` detects `MERIDIAN_SPACE_ID` to switch help/behavior:
    - **No space ID** → human mode: shows all commands including `start`, `space list/show/close`, `config`, launcher commands. Output defaults to human-readable text.
    - **Space ID set** → agent mode: shows only agent-relevant commands (`run`, `skills`, `models`, `doctor`). Space launcher commands hidden. Output defaults to JSON for programmatic piping.
    - Hidden `--human` flag forces full help (never shown to agents, documented in human help only).
14. **MCP surface = agent commands only** — `meridian serve` registers only agent-relevant operations in `server/main.py`. `start`, `space list/show/close` are never MCP tools (they launch/manage harness processes — meaningless over MCP). MCP tool responses are flat JSON (no nested metadata wrappers). MCP responses MAY include a human-readable `"warning"` field when needed; when no warning exists, the field is omitted (not `""`, not `null`). Example: `{"id": "r5", "status": "running", "warning": "WARNING [SPACE_AUTO_CREATED]: No MERIDIAN_SPACE_ID set. Created space s5. Next: set MERIDIAN_SPACE_ID=s5 for subsequent commands."}`. This is how auto-create warnings reach MCP clients (stderr is not visible over MCP). **Total: 11 MCP tools** (`run_spawn`, `run_continue`, `run_list`, `run_show`, `run_stats`, `run_wait`, `skills_list`, `skills_show`, `models_list`, `models_show`, `doctor`).
15. **Auto-create only on `run spawn`** — logic lives in the **operation layer** (`lib/ops/run.py` / `_run_prepare.py`), not just CLI — so both CLI and MCP paths get auto-create. All other commands (`run list`, `skills list`, etc.) error without space ID with a message pointing to `run spawn`.
16. **`doctor` is canonical** — standalone command, auto-repairs and reports what it did. No separate check-only mode. Both humans and agents use it. MCP tool name is `doctor`.
17. **`completion` hidden from agent help** — shell completion is a human concern, not shown in agent mode.
18. **Space status enum** — two states only: `active` (in use) and `closed` (done). No intermediate states. Replaces the current 4-state enum (`active`, `paused`, `completed`, `abandoned`). `space.json.status` can become stale if a harness crashes — `doctor` reconciles by checking flock liveness.
19. **No ambiguous top-level shortcuts** — drop `list`, `show`, `wait` shortcuts. `meridian start` is a top-level command (not a shortcut to `space start`). `meridian doctor` is standalone. Users type `meridian space list` and `meridian run show` explicitly.
20. **Output format by mode** — agent mode (`MERIDIAN_SPACE_ID` set) defaults to JSON for programmatic piping. Human mode (no space ID) defaults to human-readable text/tables. MCP tools return flat JSON (inherent to protocol), including optional `"warning"` when needed and omitted field when not needed. No `--json` flag needed.
21. **`context list` cut from MVP** — agent already has `MERIDIAN_SPACE_ID` from env var. Space metadata is available via `space show` (human mode). No agent-facing orientation command needed — the env vars are the orientation.
22. **`fs read/write/ls` cut from MVP** — agents use `$MERIDIAN_SPACE_FS/` with shell tools or harness file tools directly. Meridian is a coordination layer, not a file system. MCP clients can shell out. Plan mode file management is a harness concern, not meridian's.
23. **Scalability bound** — at >10,000 runs per space, JSONL scan may become slow (~40MB, 100ms+). Expected ceiling is well below this. If hit, add optional SQLite index layer in V2.
24. **flock portability** — advisory locks don't work reliably on NFS. Local filesystem is the supported target for MVP. Documented as known limitation.
25. **JSONL self-healing readers** — on read, truncated trailing lines (from crash mid-append) are silently skipped. Only mid-file corruption produces a warning. No doctor involvement for trailing-line truncation.
26. **Schema versioning** — `"v": 1` in JSONL events, `"schema_version": 1` in `space.json`. Forward-compatible: V2 readers can detect schema version and handle migration.
27. **Error message standard** — all agent-facing errors follow `[CODE] + cause + next action` format. Example: `ERROR [SPACE_REQUIRED]: No MERIDIAN_SPACE_ID set. Next: run 'meridian run spawn' to auto-create a space.`
28. **Security model is cooperative** — agents are assumed cooperative (same-user local trust). No hard sandbox, no capability tokens, no per-space OS isolation. Documented as known limitation. Hardened in V2 if adversarial model needed.
29. **`meridian start` auto-resume defaults + continuation behavior** — `meridian start` auto-resolves the last active space and starts a new chat there; if no active space exists, it creates a new space. `meridian start --new` always creates a new space. `meridian start --space <space-id>` selects a specific space and starts a new chat. `meridian start --continue` auto-resolves last active space and continues its last chat. `meridian start --continue <chat-id|harness-session-id>` searches across spaces for chat alias (`cN`) or raw harness session ID and resolves space + harness + params. `meridian start --space <space-id> --continue [chat-id|harness-session-id]` uses explicit space for optional disambiguation. If alias lookup is ambiguous, error: `ERROR [AMBIGUOUS_SESSION]: Chat c2 exists in multiple spaces. Next: use --space to disambiguate.` Continuation is harness-locked from session record: if `-m` routes to a different harness, error `ERROR [HARNESS_MISMATCH]: Session c2 was started with Claude. Cannot continue with a Codex model. Next: pick a model on Claude or omit -m.` Model changes are allowed within the same harness. Original session `params` are defaults; explicit passthrough flags (`--system-prompt`, `--append-system-prompt`, `-m`, etc.) override/add. Unsupported flags warn and are ignored: `WARNING [UNSUPPORTED_FLAG]: --append-system-prompt is not supported by Codex. Next: remove this flag or switch to a harness that supports it. Flag ignored.` When continuation is requested (or `run continue` is used), Meridian passes resolved `harness_session_id` to harness CLI with adapter-specific flags: `--resume <id>` for Claude, `resume <id>` for Codex, `--session <id>` for OpenCode. On auto-resolve, emit: `WARNING [SPACE_AUTO_RESUMED]: Resumed active space s3 ("feature-auth"). Next: use --new to start a fresh space.`
30. **`run spawn` + `run continue` split** — `run spawn` starts a new agent run (new conversation). `run continue <run-id>` continues a specific run's harness conversation. `run continue` (no args) continues the last run from current chat via `MERIDIAN_SESSION_ID`. `run retry` is cut entirely.
31. **Context commands cut entirely** — `context pin`, `context unpin`, and `context list` all removed from MVP. No `pinned_files` in `space.json`. Agents have `MERIDIAN_SPACE_ID` from env var — no orientation command needed. Agents manage file context explicitly via `$MERIDIAN_SPACE_FS/` and prompt references.
32. **Doctor scope narrowed** — four jobs only: (1) stale session locks, (2) orphan runs (append synthetic `finalize` with `status: "failed"`), (3) stale `space.json` status reconciliation, (4) detect space directories with missing/corrupt `space.json`, report warning, and skip those spaces (no recreate). No JSONL line repair (handled by self-healing readers).
33. **Config conventions (layered + self-documenting)** — config resolution uses layered precedence (later wins): (1) built-in defaults (hardcoded), (2) base `config.toml`, (3) override config from `--config` or `MERIDIAN_CONFIG` when supplied. `meridian init` auto-generates `config.toml` with every option present but commented out, including default values in comments. Users uncomment only what they want to override. `start.auto_resume` controls whether `meridian start` performs default auto-resolve behavior.

## File Authority Model

```
.meridian/
├── agents/            # User-authored: agent profiles
├── skills/            # User-authored: project skills
├── config.toml        # User-authored: settings
├── .gitignore         # Auto-created: gitignores runtime state, allows fs/
└── .spaces/           # Runtime: dot-prefix separates from user-authored content
    ├── .lock          # Global lock for space ID generation
    └── <space-id>/
        ├── space.lock      # Per-space lock for space.json read-modify-write
        ├── space.json      # Space metadata (runtime state, gitignored)
        ├── runs.lock       # Lock for runs.jsonl appends + run ID generation
        ├── runs.jsonl      # Append-only run log (gitignored)
        ├── sessions.lock   # Lock for sessions.jsonl appends
        ├── sessions.jsonl  # Session start/stop log (gitignored)
        ├── sessions/       # Active harness tracking (gitignored)
        │   ├── <session-id>.lock   # flock held by each harness process
        │   └── ...
        ├── runs/           # Run artifacts (gitignored, never cleaned up)
        │   └── <run-id>/
        │       ├── input.md
        │       └── output/
        └── fs/             # Agent working directory (COMMITTED — the work product)
            └── ...
```

### .meridian/.gitignore
Auto-created on first space creation:
```gitignore
.spaces/**
!.spaces/*/
!.spaces/*/fs/
!.spaces/*/fs/**
```

### space.json format
Machine-managed runtime state (not config, not user-authored):
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

Removed from MVP: `description`, `labels`, `pinned_files`, `last_activity_at`. Status derived from `finished_at` (null = active, set = closed). `id` derived from directory name but stored for convenience.

### runs.jsonl format
One JSON line per event (start or finalize). Truncated trailing lines from crash are silently skipped by readers.
```json
{"v":1,"event":"start","id":"r1","session_id":"c1","model":"claude-opus-4-6","agent":"coder","harness":"claude","harness_session_id":"<claude's conversation id>","status":"running","started_at":"2026-02-28T10:00:00Z","prompt":"..."}
{"v":1,"event":"finalize","id":"r1","status":"succeeded","exit_code":0,"duration_secs":128,"total_cost_usd":0.042,"input_tokens":4200,"output_tokens":1800,"finished_at":"2026-02-28T10:02:08Z"}
{"v":1,"event":"finalize","id":"r2","status":"failed","exit_code":1,"error":"Token limit exceeded","duration_secs":45,"finished_at":"2026-02-28T10:02:53Z"}
```

### sessions.jsonl format
One JSON line per session event. Functional state — maps meridian chat IDs to harness session IDs for `meridian start --continue` and `run continue`, and stores original continuation defaults (`harness`, `model`, `params`). Truncated trailing lines silently skipped by readers.
```json
{"v":1,"event":"start","session_id":"c1","harness":"claude","harness_session_id":"<claude's own session/conversation id>","model":"claude-opus-4-6","params":["--system-prompt","You are concise."],"started_at":"2026-02-28T10:00:00Z"}
{"v":1,"event":"start","session_id":"c2","harness":"codex","harness_session_id":"<codex's thread id>","model":"gpt-5.3-codex","params":["--append-system-prompt","Focus on tests first."],"started_at":"2026-02-28T10:05:00Z"}
{"v":1,"event":"stop","session_id":"c1","stopped_at":"2026-02-28T11:30:00Z"}
```
All appends to `sessions.jsonl` hold `flock` on `sessions.lock` in the space directory.
Liveness detection: try to acquire flock on `sessions/<session-id>.lock`. If blocked → alive. If acquired → dead (OS released on crash).

### ID generation
- Space IDs: scan `.meridian/.spaces/` directories, find max numeric suffix, increment. `s1, s2, s3` → next is `s4`.
- Run IDs: count start events in `runs.jsonl`, increment. 3 starts → next is `r4`.
- Chat IDs: count session `start` events in `sessions.jsonl`, increment. `c1, c2, c3` → next is `c4`.
- Race protection: `flock` on `.meridian/.spaces/.lock` (global lock file) during space ID generation. Per-space `runs.lock` for run ID generation and `sessions.lock` for chat ID generation.

### Run artifacts
Run artifacts (input.md, output logs) live at `.meridian/.spaces/<space-id>/runs/<run-id>/`. Never cleaned up automatically — agents grep over them. `runs.jsonl` tracks metadata; artifacts are filesystem-native. Primary agent copies important outputs to `fs/` for long-term keeping.

## Tasks

### Task Group 0: Rename Before Everything (sequential, first)

#### t00. Rename `supervisor` → `primary`/`harness` throughout codebase
- Rename all `supervisor` terminology to consistent `primary` (agent) / `harness` (process) naming
- `launch_supervisor()` → `launch_harness()` in `lib/space/launch.py`
- `build_supervisor_prompt()` → `build_primary_prompt()` in `lib/space/launch.py`
- `_resolve_supervisor_harness()` → `_resolve_harness()` in `lib/space/launch.py`
- `_build_supervisor_command()` → `_build_harness_command()` in `lib/space/launch.py`
- `MERIDIAN_SUPERVISOR_COMMAND` → `MERIDIAN_HARNESS_COMMAND` in env vars, `launch.py`, `tests/conftest.py`
- `config.supervisor.*` → `config.harness.*` in settings model and `config.toml`
- `supervisor_agent` → `primary_agent` in `tests/fixtures/config/settings.toml` and settings model
- `supervisor_default_tier` → `primary_default_tier` (or `harness_default_tier`)
- Update all test files that reference supervisor terminology
- Update all docstrings and comments
- **Dependencies**: none (must run first, before any other task)
- **Test**: `uv run pytest` (full suite — this is a rename, everything must still pass)
- **Scope**: M (mechanical but wide-reaching — ~30+ occurrences across source + tests + config)

### Task Group A: Build File Authority (parallel, after t00)

#### t01. Space file model
- Create `lib/space/space_file.py` — parse/write `space.json` (stdlib `json` only)
- `create_space()` → writes `space.json`, creates `fs/` dir, ensures `.meridian/.gitignore` exists
- `get_space()` → reads `space.json`
- `list_spaces()` → scans `.meridian/.spaces/*/space.json`
- `transition_space()` → updates `space.json` status field (two states only: `active`, `closed`)
- All writes use atomic pattern: write to `space.json.tmp` → `os.rename()` → done
- All read-modify-write operations (status change) hold `flock` on `space.lock` in the space directory
- Include `schema_version: 1` in space.json
- `doctor` corruption recovery: if `space.json` is invalid JSON, report and skip (don't crash)
- Space metadata is identity + lifecycle only — no pinned files, labels, description, or agent/supervisor tracking
- Change `SpaceState` enum in `domain.py` from `Literal["active", "paused", "completed", "abandoned"]` to `Literal["active", "closed"]`
- Update transition table in `space/crud.py` to match 2-state model
- Create `tests/test_space_file_model.py`
- **Dependencies**: t00
- **Test**: `uv run pytest tests/test_space_file_model.py`
- **Scope**: M

#### t02. Run file model
- Create `lib/state/run_store.py` — read/write `runs.jsonl`
- `start_run()` → appends start event (with `flock` on `runs.lock` in space dir)
- `finalize_run()` → appends finalize event (with `flock` on `runs.lock`)
- ID generation + event append must be ONE atomic operation under ONE flock hold (no TOCTOU)
- `list_runs()` → parse JSONL, filter by space/status/model. Run status is derived from last event for that run ID. Truncated trailing lines silently skipped (self-healing reader).
- `get_run()` → parse JSONL, find by ID
- `run_stats()` → parse JSONL, aggregate in Python
- All events include `"v": 1` for schema versioning
- `space_spend_usd()` → sum `total_cost_usd` from finalize events
- Create `tests/test_state/test_run_store.py`
- **Dependencies**: t00
- **Test**: `uv run pytest tests/test_state/test_run_store.py`
- **Scope**: M

#### t03. File-based ID generation
- Rewrite `state/id_gen.py` — drop `sqlite3.Connection` param
- `next_space_id(repo_root)` → scan `.meridian/.spaces/` dirs, generate `s`-prefixed IDs (replaces `w`-prefix)
- `next_run_id(space_dir)` → count starts in `runs.jsonl` (called within flock held by `run_store.start_run()`)
- Existing `w`-prefixed spaces are not migrated — clean break per project philosophy
- Create `tests/test_state/test_id_file.py`
- **Dependencies**: t00
- **Test**: `uv run pytest tests/test_state/test_id_file.py`
- **Scope**: S

#### t04. File-authority path helpers
- Create `lib/state/paths.py` — resolve `.meridian/.spaces/<id>/`, `runs.jsonl`, `sessions/`, `fs/`, etc.
- Replace `resolve_state_paths()` and `resolve_run_log_dir()` from deleted `state/db.py`
- Include `.meridian/.gitignore` creation helper (called by `create_space()` in t01)
- Create `tests/test_state/test_paths.py`
- **Dependencies**: t00
- **Test**: `uv run pytest tests/test_state/test_paths.py`
- **Scope**: S

#### t04b. Session tracking model
- Create `lib/space/session_store.py` — manage harness sessions per space
- `start_session()` → under one critical section with `flock` on `sessions.lock`, appends start event to `sessions.jsonl` (including `harness_session_id`, `harness`, `model`, `params`), then acquires flock on `sessions/<id>.lock`
- `stop_session()` → under `flock` on `sessions.lock`, appends stop event, releases flock on `sessions/<id>.lock`
- `list_active_sessions()` → scan `sessions/*.lock`, try-acquire to detect liveness
- `get_last_session()` → find most recent chat for `meridian start --space <space-id> --continue` without explicit chat ID
- `resolve_session_ref()` → resolve `--continue` input as chat alias (`cN`) or raw harness session ID, across all spaces or within explicit `--space`; returns target space + session + continuation defaults
- `get_session_harness_id()` → lookup `harness_session_id` for a given chat ID (used by `run continue`)
- `cleanup_stale_sessions()` → find dead locks, write stop events, delete lock files
- All events include `"v": 1` for schema versioning. Truncated trailing lines silently skipped.
- Create `tests/test_space/test_session_store.py`
- **Dependencies**: t00
- **Test**: `uv run pytest tests/test_space/test_session_store.py`
- **Scope**: M

#### t05. Skill registry filesystem scan
- Rewrite `config/skill_registry.py` — replace SQLite index with directory scan of skill files
- Remove `skills reindex` command and operation from `ops/skills.py` and CLI
- **Dependencies**: t00
- **Test**: `uv run pytest tests/test_cli_skills_models.py`
- **Scope**: M

### Task Group B: Rewrite Consumers (depends on A)

#### t06. Rewire operation runtime
- Modify `lib/ops/_runtime.py` — remove SQLite stores, wire to file-based readers
- Remove dead `space_store`/`context_store` fields
- Modify `lib/state/__init__.py` — update exports
- Modify `lib/adapters/__init__.py` — update exports
- **Dependencies**: t01, t02, t03, t04, t04b
- **Test**: `uv run pytest tests/test_state_paths.py`
- **Scope**: M

#### t07. Rewrite space domain (crud, summary)
- Modify `lib/space/crud.py` — delegate to `space_file.py` (replace `StateDB` param with file-based calls: `create_space()`, `resolve_space_for_resume()`, `transition_space()`)
- Delete `lib/space/context.py` — context commands cut entirely from MVP
- Modify `lib/space/summary.py` — remove or simplify (no markdown body to write to; summary goes to `fs/` if needed)
- Modify `lib/prompt/reference.py` — replace import of `session_files.py` helpers with `$MERIDIAN_SPACE_FS/`-based file resolution (resolve `@file` references against space `fs/` directory instead of old session-scoped paths)
- **Dependencies**: t06
- **Test**: `uv run pytest tests/test_space_slice6.py tests/test_prompt_slice3.py`
- **Scope**: M

#### t08. Rewrite space ops and launch
- Modify `lib/ops/space.py` — replace SQLite reads in `space_show_sync` (include session history with copy-paste continue commands), replace session file ops with `session_store.py`, wire `space close` to clean up all sessions. Remove `space.write`, `space.read`, `space.files` operation registrations (cut from MVP — agents use `$MERIDIAN_SPACE_FS/` directly). Remove `space resume` as separate operation (folded into `meridian start --space ...` behavior).
- Modify `lib/space/launch.py`:
  - **Replace `os.execvp` (TTY path) with `subprocess.Popen` + `wait()`** — this is required for session tracking and cleanup to work. No pipes — child inherits terminal for full interactive passthrough.
  - Remove Claude-only harness restriction
  - Add `MERIDIAN_SPACE_FS` and `MERIDIAN_SESSION_ID` env vars to `_build_harness_env()` (renamed from `_build_space_env()`)
  - Default launch is fresh conversation; when `--continue` is explicitly requested, pass mapped `harness_session_id` through harness adapter flags
  - Simplify state transitions to 2-state model (active/closed) — remove `paused`/`abandoned` transitions
  - Call `start_session()` on harness launch (records `harness_session_id`), call `cleanup_stale_sessions()` on start
- **Dependencies**: t07
- **Test**: `uv run pytest tests/test_space_launch_sliceb.py tests/test_space_files_slice7.py`
- **Scope**: L

#### t09. Rewrite run query/list/stats paths
- Modify `lib/ops/run.py` — replace `run_list_sync`, `run_stats_sync`, `run_show_sync` with JSONL reads
- Modify `lib/ops/_run_query.py` — replace `_read_run_row()`, `_detail_from_row()` with JSONL reads
- Implement `run continue <run-id>` — lookup run's chat (`session_id`), resolve `harness_session_id` from run/session state, pass to harness adapter. `run continue` (no args) uses `MERIDIAN_SESSION_ID` to find last run from current chat.
- Keep `run spawn` as explicit new-conversation command. Remove continuation flags from `run spawn`, and remove `run retry`.
- **Dependencies**: t06 (not t08 — run query paths are independent of space ops)
- **Test**: `uv run pytest tests/test_run_stats.py tests/test_run_wait_multi.py`
- **Scope**: L

#### t10. Rewrite run execute/finalize paths
- Modify `lib/ops/_run_execute.py` — replace `_space_spend_usd()`, `resolve_run_log_dir()` usage with file-based equivalents
- Modify `lib/exec/spawn.py` — replace `StateDB.append_start_row`, `StateDB.append_finalize_row` with `run_store` calls
- **Dependencies**: t06 (independent of t09 — execute/finalize path doesn't depend on query path)
- **Test**: `uv run pytest tests/test_exec_slice4.py tests/test_exec_slice5a.py`
- **Scope**: L

#### t11. Rewrite diagnostics, delete context ops
- Modify `lib/ops/diag.py` — four jobs only: (1) stale session locks (cleanup + append stop events), (2) orphan runs (start without finalize → append synthetic `finalize` with `status: "failed"`), (3) stale `space.json` status reconciliation, (4) detect missing/corrupt `space.json` in space dirs, report warning, and skip those spaces (no recreate). No JSONL line repair (handled by self-healing readers). Auto-repairs and reports what it did.
- Delete `lib/ops/context.py` — all context commands cut from MVP (pin/unpin/list). Agent has `MERIDIAN_SPACE_ID` from env var.
- Delete `cli/context.py` — remove context CLI group entirely.
- **Dependencies**: t06 (independent of t10 — diag/context don't depend on execute paths)
- **Test**: `uv run pytest tests/test_space_slice6.py -k "diag or context"`
- **Scope**: M

#### t12. Rewrite config paths that import state/db
- Modify `lib/config/_paths.py` — remove `state/db.py` import, use new `state/paths.py`
- Modify `lib/config/catalog.py` — same
- Modify `lib/config/settings.py` — same
- Modify `lib/ops/config.py` — same
- Modify `tests/test_config_slice2.py` — imports `meridian.lib.state.db`, needs update
- Modify `tests/test_config_s4b_env_overrides.py` — imports `meridian.lib.adapters.sqlite`, needs update
- **Dependencies**: t04
- **Test**: `uv run pytest tests/test_config_settings.py tests/test_config_slice2.py`
- **Scope**: S

#### t13. Delete SQLite infrastructure
- Delete `lib/state/db.py`
- Delete `lib/state/schema.py`
- Delete `lib/state/jsonl.py`
- Delete `lib/adapters/sqlite.py` (~900 lines)
- Delete `lib/ops/migrate.py`
- Delete `cli/migrate.py`
- Delete `cli/export.py`
- Delete `lib/space/session_files.py`
- Remove migrate/export from `lib/ops/registry.py` bootstrap (lazy import at `:78`)
- Remove from `cli/main.py`: imports at lines 19-20, command group wiring at 200-201, registration at 320 and 409
- Remove `skills reindex` operation from registry if not already handled by t05
- **Dependencies**: t06-t12 (all consumers rewritten first)
- **Test**: `uv run pytest tests/test_cli_smoke.py tests/test_surface_parity.py`
- **Scope**: L

### Task Group C: CLI + Tests (partially parallel with B)

#### t14. Delete fs and context command groups
- Delete `cli/fs.py` if it exists (fs commands cut from MVP)
- Delete `lib/ops/fs.py` if it exists
- Delete `cli/context.py` if not already handled by t11
- Modify `cli/space.py` — remove `read/write/files` subcommands
- Modify `cli/main.py` — remove `fs` and `context` group registrations
- Update `lib/ops/registry.py` — remove fs and context operation registrations
- **Dependencies**: t08 (space ops done, which also removes `space.write/read/files` operation registrations from `ops/space.py`)
- **Test**: `uv run pytest tests/test_cli_smoke.py`
- **Scope**: S

#### t14b. Context-aware CLI and MCP surface
- Modify `cli/main.py` — detect `MERIDIAN_SPACE_ID` to switch help rendering and output format:
  - Agent mode (space ID set): show only `run`, `skills`, `models`, `doctor`. Default output to JSON.
  - Human mode (no space ID): show all commands including `start`, `space list/show/close`, `config`, `init`, `serve`. Default output to human-readable text.
  - Hidden `--human` flag to force full help (not in agent-mode help output)
- Implement `meridian start` as top-level command (not shortcut to `space start`):
  - `meridian start` → auto-resolve last active space + new chat, or create new space if none active
  - `meridian start --new` → force create new space (skip auto-resolve)
  - `meridian start --space <space-id>` → explicit space + new chat
  - `meridian start --continue` → auto-resolve last active space + continue last chat
  - `meridian start --continue <chat-id|harness-session-id>` → search across spaces + continue specific chat/session
  - `meridian start --space <space-id> --continue` → optional disambiguation: explicit space + continue last chat
  - `meridian start --space <space-id> --continue <chat-id|harness-session-id>` → optional disambiguation: explicit space + continue specific chat/session
  - If alias is ambiguous across spaces: `ERROR [AMBIGUOUS_SESSION]: Chat c2 exists in multiple spaces. Next: use --space to disambiguate.`
  - Enforce harness lock from original session: `ERROR [HARNESS_MISMATCH]: Session c2 was started with Claude. Cannot continue with a Codex model. Next: pick a model on Claude or omit -m.`
  - Preserve original session `params` as baseline; explicit passthrough flags are additive/overriding
  - Unsupported passthrough flags emit warning and are ignored: `WARNING [UNSUPPORTED_FLAG]: --append-system-prompt is not supported by Codex. Next: remove this flag or switch to a harness that supports it. Flag ignored.`
  - Emit warning on auto-resolve: `WARNING [SPACE_AUTO_RESUMED]: Resumed active space s3 ("feature-auth"). Next: use --new to start a fresh space.`
  - Model/agent/skills pass through independently of `--space`/`--continue`/`--new`
- Remove `space resume` as separate command
- Remove `context pin`, `context unpin` from CLI and MCP
- Remove `run retry` as separate command
- Modify `lib/ops/registry.py` — add `mcp_visible=False` to space ops (`space_start`, `space_close`, `space_list`, `space_show`) and config ops
- Modify **`server/main.py`** — filter MCP tool registration by `mcp_visible` (this is where MCP tools are actually registered, NOT `cli/main.py`). **Total: 11 MCP tools.**
- Rename `diag` group → `doctor` as canonical command (remove shortcut indirection)
- Hide `completion` group from agent-mode help
- Implement error message standard: `[CODE] + cause + next action` for all agent-facing errors
- **Dependencies**: t13 (clean slate)
- **Test**: `uv run pytest tests/test_cli_smoke.py tests/test_surface_parity.py`
- **Scope**: M

#### t15. Auto-create space + enforce explicit space on run commands
- Auto-create logic lives in **operation layer** (`lib/ops/run.py` or `lib/ops/_run_prepare.py`), NOT just CLI — both CLI and MCP paths must get auto-create behavior
- If no `--space` and no `MERIDIAN_SPACE_ID`:
  - Auto-create space via `create_space()`
  - Emit warning: `"WARNING [SPACE_AUTO_CREATED]: No MERIDIAN_SPACE_ID set. Created space {id}. Next: set MERIDIAN_SPACE_ID={id} for subsequent commands."`
  - Proceed with run
- All other commands error without space ID: `"ERROR [SPACE_REQUIRED]: No MERIDIAN_SPACE_ID set. Next: run 'meridian run spawn' to auto-create a space, or set MERIDIAN_SPACE_ID."`
- Modify `lib/ops/_run_models.py` — space is resolved (auto or explicit), never None
- **Dependencies**: t09, t01
- **Test**: `uv run pytest tests/test_cli_run_stats.py`
- **Scope**: S

#### t16. Rewrite state-layer tests
- Modify `tests/test_state/test_state_layer.py` — replace SQLite fixtures with file-based state
- Modify `tests/test_state_paths.py`
- Delete `tests/test_migrate_slice7.py`
- **Dependencies**: t14b
- **Test**: `uv run pytest tests/test_state/`
- **Scope**: L

#### t17. Rewrite run-layer tests
- Modify `tests/test_run_stats.py`, `test_run_wait_multi.py`, `test_run_reference_resolution.py`
- Modify `tests/test_run_output_streaming.py`
- Modify `tests/test_exec_slice4.py`, `test_exec_slice5a.py`
- Modify `tests/test_safety_slice7.py`
- **Dependencies**: t13, t15
- **Test**: `uv run pytest tests/test_run_stats.py tests/test_run_wait_multi.py tests/test_safety_slice7.py`
- **Scope**: L

#### t18. Rewrite space and CLI integration tests
- Modify `tests/test_space_slice6.py`, `test_space_launch_sliceb.py`, `test_space_files_slice7.py`
- Modify `tests/test_cli_smoke.py`, `test_cli_run_stats.py`, `test_cli_run_wait_multi.py`
- Modify `tests/test_surface_parity.py`
- **Dependencies**: t14, t16
- **Test**: `uv run pytest tests/test_space_slice6.py tests/test_cli_smoke.py tests/test_surface_parity.py`
- **Scope**: L

#### t19. Final cleanup and regression
- Modify `CLAUDE.md` — update philosophy (no SQLite mention)
- Remove any remaining `import sqlite3` in `src/`
- Verify `meridian serve` (MCP) works with renamed operations
- Full test suite pass
- **Dependencies**: t17, t18
- **Test**: `uv run pytest`
- **Scope**: M

## Execution Strategy

### How to Execute

Run `/orchestrate plans/new-philosophy/implementation/plan.md` to execute this plan. The orchestrator follows the steps below, using `run-agent.sh` to dispatch implementation and review work to codex/opus agents.

**Living document**: The orchestrator may rewrite this plan at any time during execution — reordering tasks, splitting/merging steps, updating decisions, or adding new tasks discovered during implementation. The plan reflects current understanding, not a frozen spec.

### Orchestration Model

Each step follows implement → review → decide:

1. **Implement**: 1 codex agent (default) or opus for subtle correctness tasks
2. **Review fan-out**: 2-3 codex agents in parallel, each with a different focus:
   - **Correctness review**: does the implementation match the task spec?
   - **SOLID review**: does it follow SOLID principles, use proper abstractions?
   - **Plan adherence review**: does it conform to the overall plan decisions and reference docs?
3. **Decide**: orchestrator reads all review reports and decides:
   - **Ship**: reviews pass or issues are minor/cosmetic → commit and move to next task
   - **Rework**: genuine issues found → launch targeted fix run, then re-review (lighter)
   - **Skip**: review identifies issues that are out-of-scope for this task → note and move on
   - Reviews are advisory, not blocking. The orchestrator owns the decision. It is fine to leave review findings unaddressed if they are cosmetic, out of scope, or would cause scope creep. Max 3 rework cycles per task before escalating to user.

### Implementation Steps

#### Step 1: Rename `supervisor` → `primary`/`harness` (t00)

**Why first**: mechanical find-replace, zero dependencies, clears terminology confusion for everything after.

- **Implement**: 1 codex — find-replace across ~30+ occurrences in source, tests, config, docstrings
- **Review**: 2 codex — (1) grep for any remaining `supervisor` occurrences, (2) verify tests still pass and no semantic breakage
- **Gate**: `uv run pytest` full suite passes
- **CLI smoke**: `uv run meridian --help` — verify no `supervisor` in output

#### Step 2: Delete dead commands (t05, t11 deletions, t14 deletions)

**Why second**: reduce surface area before building new abstractions. Less code = less to refactor.

Consolidates deletion work from multiple tasks:
- Delete `cli/migrate.py`, `cli/export.py`, `cli/context.py`
- Delete `ops/migrate.py`, `ops/context.py`
- Remove `run retry` from `cli/run.py` and `ops/run.py`
- Remove `skills reindex` from `cli/skills_cmd.py` and `ops/skills.py`
- Remove `space.read/write/files` from `cli/space.py` and `ops/space.py`
- Remove all associated registrations from `ops/registry.py` and `cli/main.py`
- Remove `fs` and `context` group registrations

- **Implement**: 1 codex — systematic deletion with grep verification
- **Review**: 2 codex — (1) grep for any remaining references to deleted commands in non-deletion context, (2) verify imports still resolve and no startup crashes
- **Gate**: `uv run pytest tests/test_cli_smoke.py` passes (CLI loads without errors)
- **CLI smoke**: `uv run meridian migrate run` should error cleanly (command not found); `uv run meridian --help` should not list deleted commands

#### Step 3: Extract store protocols (SOLID prerequisite)

**Why third**: create the abstraction seams BEFORE implementing file-backed stores. This is the DIP/ISP fix that enables clean storage swap.

New work:
- Define `RunStore`, `SpaceStore`, `SessionStore` protocols (abstract interfaces)
- Extract current SQLite implementations behind these protocols (don't change behavior yet)
- Make ops depend on protocols, not concrete types
- Refactor `_runtime.py` to use constructor-injected protocols instead of hardcoded SQLite types
- Split fat `HarnessAdapter` interface into focused protocols (command building, stream parsing, usage extraction)

- **Implement**: 1 codex (or opus if interface design is subtle)
- **Review**: 3 codex — (1) protocol completeness (do interfaces cover all ops usage?), (2) SOLID compliance (no concrete types leaked through protocols), (3) plan adherence (protocols match planned file-authority model)
- **Gate**: `uv run pytest` full suite passes (behavior unchanged, just abstracted)

#### Step 4: Implement file-backed stores (t01, t02, t03, t04, t04b)

**Why fourth**: now that protocols exist, implement the file-authority versions. These tasks are independent and can run in parallel.

- **t01** Space file model (`space_file.py`) — space.json CRUD, atomic writes, locking
- **t02** Run file model (`run_store.py`) — runs.jsonl read/write, self-healing reader
- **t03** File-based ID generation (`id_gen.py` rewrite) — scan-based IDs
- **t04** Path helpers (`paths.py`) — resolve all `.meridian/.spaces/` paths
- **t04b** Session tracking (`session_store.py`) — sessions.jsonl, chat aliases, continuation resolution
- **t05** Skill registry filesystem scan (`skill_registry.py` rewrite)

- **Implement**: up to 3 codex in parallel (t01+t02+t03 as batch 1, t04+t04b+t05 as batch 2, or all 6 if file conflicts are minimal)
- **Review**: 2 codex per batch — (1) correctness (locking, atomicity, self-healing), (2) plan adherence (schema matches plan examples, field names match)
- **Gate**: per-task unit tests pass

#### Step 5: Wire file stores + delete SQLite (t06, t12, t13)

**Why fifth**: swap the composition root from SQLite to file-backed, then delete all SQLite infrastructure.

- **t06** Rewire `_runtime.py` — inject file-backed stores into protocols
- **t12** Fix config imports — `config/_paths.py`, `catalog.py`, `settings.py` use new `paths.py`
- **t13** Delete SQLite — `adapters/sqlite.py`, `state/db.py`, `state/schema.py`, `state/jsonl.py` (old), `cli/migrate.py`, `cli/export.py` (if not already gone from step 2)

- **Implement**: 1 codex for t06+t12 (related wiring), then 1 codex for t13 (deletion)
- **Review**: 2 codex — (1) grep for any remaining `sqlite3`/`StateDB`/`SQLiteRunStore` imports, (2) verify full test suite
- **Gate**: `uv run pytest` full suite, zero `sqlite3` imports in `src/meridian/`
- **CLI smoke**: `uv run meridian --help` — verify CLI starts with no SQLite; `python -c "import meridian"` — no import errors

#### Step 6: Rewrite consumers (t07, t08, t09, t10)

**Why sixth**: now that file stores are wired, rewrite the business logic that uses them.

- **t07** Space domain — `crud.py` delegates to `space_file.py`, delete `context.py`, simplify `summary.py`
- **t08** Space ops/launch — `ops/space.py` uses file stores, `launch.py` uses `subprocess.Popen`, session tracking integration
- **t09** Run query paths — `run_list_sync`, `run_stats_sync`, `run_show_sync` use JSONL reads; implement `run continue`
- **t10** Run execute/finalize — `_run_execute.py` and `spawn.py` use `run_store` calls

t07→t08 are sequential. t09 and t10 can run in parallel with each other and with t07/t08.

- **Implement**: 1 codex for t07→t08 (sequential), 1 codex for t09, 1 codex for t10 (parallel)
- **Review**: 2 codex — (1) SOLID compliance (no raw SQL, no concrete store imports in ops), (2) plan adherence (run continue semantics, session tracking, subprocess.Popen)
- **Gate**: per-task test suites pass

#### Step 7: CLI reshape + MCP (t14b, t15)

**Why seventh**: clean slate — all storage is file-backed, all dead commands deleted, consumers rewritten.

- **t14b** Context-aware CLI and MCP surface:
  - Human vs agent help based on `MERIDIAN_SPACE_ID`
  - `meridian start` with `--space/--continue/--new` + auto-resume
  - `run spawn` + `run continue` as separate commands
  - Standalone `doctor` command
  - MCP restricted to 11 tools
  - Error message standard `[CODE] + cause + next action`
  - Harness-locked continuation with `[HARNESS_MISMATCH]`, `[AMBIGUOUS_SESSION]`, `[UNSUPPORTED_FLAG]`

- **t15** Auto-create space on `run spawn` (operation layer)

- **Implement**: 1 codex (or opus — CLI UX is design-sensitive)
- **Review**: 3 codex — (1) CLI behavior matches cli-spec.md exactly, (2) MCP tool count = 11 with correct names, (3) error/warning format compliance
- **Gate**: `uv run pytest tests/test_cli_smoke.py tests/test_surface_parity.py`
- **CLI smoke**: Full CLI exercise in a temp dir:
  - `uv run meridian --help` (human mode — full help, text output)
  - `MERIDIAN_SPACE_ID=test uv run meridian --help` (agent mode — restricted commands, JSON default)
  - `uv run meridian doctor` (should work standalone)
  - `uv run meridian start --new --dry-run` (if dry-run supported, else just verify it doesn't crash on missing harness)
  - `uv run meridian serve --help` (MCP help)

#### Step 8: Rewrite tests (t16, t17, t18)

**Why eighth**: all production code is stable — now fix tests to match.

- **t16** State-layer tests — replace SQLite fixtures with file-based
- **t17** Run-layer tests — update run stats, wait, safety tests
- **t18** Space and CLI integration tests — update space, launch, CLI smoke tests

These can run in parallel (independent test files).

- **Implement**: up to 3 codex in parallel (one per test group)
- **Review**: 1 codex — verify all tests pass, no skipped/xfail hacks
- **Gate**: `uv run pytest` full suite green

#### Step 9: Final cleanup (t19)

**Why last**: sweep for stragglers.

- Update `CLAUDE.md` — remove SQLite mentions from philosophy
- Grep for any remaining `import sqlite3` in `src/`
- Verify `meridian serve` (MCP) works
- Full regression

- **Implement**: 1 codex
- **Review**: 1 codex — final grep for sqlite, supervisor, stale imports
- **Gate**: `uv run pytest` full suite, clean grep
- **CLI smoke**: End-to-end in temp dir:
  - `uv run meridian start --new` → verify space created under `.meridian/.spaces/`
  - Verify `space.json` written with correct schema
  - `MERIDIAN_SPACE_ID=<id> uv run meridian run spawn --harness claude --model sonnet -p "test"` (will fail on harness, but should get past CLI parsing + space auto-create)
  - `uv run meridian doctor` → clean report
  - `uv run meridian space list` → shows the created space

### Dependency Graph

```
Step 1 (rename)
  ↓
Step 2 (delete dead commands)
  ↓
Step 3 (extract store protocols)
  ↓
Step 4 (implement file stores)     ← parallel: t01, t02, t03, t04, t04b, t05
  ↓
Step 5 (wire + delete SQLite)      ← sequential: t06 → t12 → t13
  ↓
Step 6 (rewrite consumers)         ← partial parallel: t07→t08, t09, t10
  ↓
Step 7 (CLI reshape + MCP)         ← sequential: t14b → t15
  ↓
Step 8 (rewrite tests)             ← parallel: t16, t17, t18
  ↓
Step 9 (final cleanup)
```

### Review Philosophy

- Reviews are **advisory, not blocking**. The orchestrator reads all reports and makes the call.
- Cosmetic issues, style nits, and out-of-scope improvements are noted but not fixed.
- SOLID violations introduced by the current task are fixed. Pre-existing SOLID violations are noted but not fixed (unless they block the task).
- Plan adherence is checked against reference docs — if implementation diverges from plan decisions, that's a genuine issue.
- Max 3 rework cycles per task. If reviews don't converge after 3 cycles, escalate to user.
- The goal is **progress over perfection**. Ship when good enough, iterate later.

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Harness crash leaves space `active` | Spaces stuck `active` | Use `subprocess.Popen` (no pipes, child inherits terminal) + `wait()` instead of `execvp` — meridian can do cleanup after harness exits. Session flock released by OS on crash. `doctor` sweeps stale sessions as fallback |
| Concurrent JSONL writes from multiple agents | Corrupted lines | `flock` on `runs.lock` in `run_store.py`. ID generation + append in single critical section |
| `space.json` concurrent modification | Lost updates | `flock` on `space.lock` + atomic write (`.tmp` → `os.rename()`) |
| `space.json` corruption (crash mid-write) | Unreadable space | Atomic write pattern prevents partial writes. `doctor` reports corrupted spaces |
| Test rewrite scope larger than estimated | Timeline slip | Parallelize test updates across codex runs |
| ID generation race conditions | Duplicate IDs | Global lock for space IDs, per-space `runs.lock` for run IDs. Lock held through read+append |
| `exec/spawn.py` has deep StateDB coupling | Missed breakage | Import graph traced; t10 covers explicitly |
| `config/skill_registry.py` has own SQLite | Missed dependency | t05 covers this; rip out entirely |
| `ops/registry.py` lazy-imports migrate | Startup crash if not removed | t13 removes registry entry |
| Parallel codex agents modify shared files | Merge conflicts | t00 rename runs first (single agent). Group A tasks don't share files. `domain.py` state enum change is in t01 only |
| Root `.gitignore` blocks nested carve-outs | `fs/` not committed | Documented constraint: root `.gitignore` must NOT contain `.meridian/` |
| flock doesn't work on NFS | Session liveness broken | Documented as known limitation — local filesystem only for MVP |

## Non-Goals (explicitly deferred)

- SQLite cache/index layer — not needed at this scale; at >10k runs per space, consider adding in V2
- All `fs` commands — cut from MVP; agents use native tools + `$MERIDIAN_SPACE_FS/`
- Cross-space search/aggregation — agents grep `.meridian/.spaces/*/runs/` directly
- Codex/OpenCode E2E testing — harnesses have upstream blockers
- Video walkthroughs / extensive docs phase
- Agent communication protocol beyond shared `fs/`
- Harness lifecycle hooks / error normalization (noted in review, defer to post-refactor)
- CLI REPL for multi-session management — skipped in favor of web UI (see Roadmap)
- Multi-space orchestration from within a harness — possible via shell (agent can run `meridian start`) but not explicitly supported in MVP. Design properly in V2
- Migration of existing `w`-prefixed spaces — clean break per project philosophy
- All context commands (`context list/pin/unpin`) — cut from MVP; agents use `MERIDIAN_SPACE_ID` + `$MERIDIAN_SPACE_FS/` and prompt references
- `run retry` — users manually retry with `run spawn`
- `space.json.description`, `space.json.labels` — no current consumer, add in V2
- Cross-space `run stats --all-spaces` — available per-space only; cross-space aggregation requires scripting
- Launcher CLI/PTY split — premature for MVP, design in V2 when web UI needs it
- Adversarial agent security model — cooperative trust for MVP, hardened sandbox in V2

## Roadmap

### MVP (this plan): File-based foundation
- Files as authority, no SQLite
- CLI: `meridian start` → subprocess (not execvp) → one harness, PTY passthrough
- `meridian start` defaults to auto-resolve last active space (or create new if none), `--new` forces fresh space
- `meridian start --space` and `--continue` support explicit-space launch/continuation
- Context-aware help and output format (human mode = text, agent mode = JSON)
- Agent CLI: run, skills, models, doctor
- `run spawn` (new conversation) + `run continue` (conversation continuation)
- `meridian serve` exposes agent commands as MCP tools (11 tools)
- Foundation: space.json, runs.jsonl, sessions.jsonl (with harness_session_id), flock-based session tracking
- Schema versioning (`v: 1` in JSONL, `schema_version: 1` in space.json)
- JSONL self-healing readers (truncated trailing lines skipped)
- Structured error messages (`[CODE] + cause + next action`)
- Cooperative security model (documented limitation)

### V2: Web UI — multi-session manager
- `meridian serve` expands to REST + websocket API
- Web dashboard: create spaces, manage sessions, view runs/costs
- Embedded terminal panes (xterm.js) with direct PTY passthrough per harness session
- User clicks "New Space" → API calls `space create` + `session add`
- Each harness renders in its own terminal pane — harness doesn't know it's in a browser
- CLI remains for: agents inside harnesses, humans who prefer terminal, quick single-harness launch

### Design notes for V2
- The CLI doesn't need REPL or attach commands — the web UI replaces that need entirely
- `meridian start` stays simple (auto-resolve/create space based on flags + launch one harness in current terminal)
- `meridian serve` becomes the backend for both MCP clients and the web UI
- All state is files — UI reads the same space.json/runs.jsonl/sessions.jsonl the CLI writes
- PTY management lives in the serve layer, not in the CLI

## Reference Docs

All reference docs describe **post-refactor target state** and have been updated to reflect this plan:
- **reference/architecture.md** — storage layout, session tracking, git behavior, command surface
- **reference/behaviors.md** — space/run/session lifecycle, `$MERIDIAN_SPACE_FS/` file access, env vars, context-aware CLI
- **reference/cli-spec.md** — complete CLI specification with human/agent modes, MCP surface, output format
- **reference/gaps.md** — remaining gaps after this plan is complete
- **reference/mvp-scope.md** — in-scope/out-of-scope/acceptance criteria
- **reference/codex-blockers.md** — re-validate during implementation (dated 2025)
- **REVIEW-SYNTHESIS.md** — review findings from 4x codex + 1x opus cross-examination
