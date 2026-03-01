# Meridian-Channel MVP Scope

**Status:** Post-refactor target state (2026-02-28)

## MVP Goal

Ship a single-phase refactor where Meridian is a files-only coordination layer with explicit space context, multi-harness sessions, and no SQLite dependencies.

## In Scope

### 1. Files as sole authority

- Runtime state under `.meridian/.spaces/<space-id>/`
- `.spaces/.lock` for global space ID generation
- `space.lock` for per-space `space.json` read-modify-write
- `space.json` for space metadata
- `runs.lock` for run ID generation + `runs.jsonl` appends
- `runs.jsonl` for run events
- `sessions.jsonl` + `sessions.lock` + `sessions/<session-id>.lock` for session tracking/liveness
- No SQLite cache/index anywhere

### 2. Space metadata format

`space.json` fields:
- `schema_version` (always `1` for MVP)
- `id`
- `name`
- `status`
- `started_at`
- `finished_at`

No `supervisor` field. Status is `active` or `closed` only. Removed from MVP: `description`, `labels`, `pinned_files`, `last_activity_at`.

### 3. Multi-harness session model

- Multiple concurrent harness sessions per space
- Lock-based liveness via `flock`
- Stale session cleanup on start/resume
- Full cleanup on close

### 4. Command surface updates

- `meridian start` as top-level launch command (auto-resolves last active space + new chat, or creates new space if none active)
- `meridian start --new` to force creation of a fresh space
- `meridian start --space <space-id>` to use an explicit space with a new chat
- `meridian start --continue` to auto-resolve last active space and continue last chat
- `meridian start --continue <chat-id|harness-session-id>` to resolve continuation target across spaces
- `meridian start --space <space-id> --continue [chat-id|harness-session-id]` to disambiguate/limit lookup to explicit space
- `--continue` is harness-locked: harness comes from the original session record, model can change only within that harness
- Continuation passthrough flags are additive: original session params are defaults, explicit flags override; unsupported flags warn and are ignored
- `run spawn` starts a new run conversation; `run continue [run-id]` continues a run conversation
- Remove `space read/write/files`, `fs read/write/ls`, `space start/resume`, `run retry`, `context list/pin/unpin`
- Context-aware CLI mode based on `MERIDIAN_SPACE_ID`:
  - Human mode (no `MERIDIAN_SPACE_ID`) shows full command surface, outputs human-readable text
  - Agent mode (`MERIDIAN_SPACE_ID` set) shows only agent-relevant commands, outputs JSON
- MCP surface registers agent-mode commands only (11 tools)
- `doctor` is canonical command (renamed from `diag repair`)
- Auto-create space on `run spawn` when `MERIDIAN_SPACE_ID` is missing
- Auto-resolve warning on `meridian start`: `WARNING [SPACE_AUTO_RESUMED]: Resumed active space s3 ("feature-auth"). Next: use --new to start a fresh space.`
- `completion` is hidden from agent-mode help
- Hidden `--human` flag forces full help output
- Error messages follow `[CODE] + cause + next action` format
- Config conventions in scope: layered merge (defaults → `config.toml` → override from `--config` or `MERIDIAN_CONFIG`) and `meridian init` writing a fully commented, self-documenting `config.toml` template

### 5. Git behavior

Auto-create `.meridian/.gitignore`:

```gitignore
.spaces/**
!.spaces/*/
!.spaces/*/fs/
!.spaces/*/fs/**
```

**Constraint:** Repo root `.gitignore` must NOT contain `.meridian/` — parent ignores block nested carve-outs.

Effect:
- Runtime metadata/logs/artifacts are ignored
- `fs/` is committed (agent work product)

### 6. Run artifact policy

- Run artifacts live in `runs/<run-id>/`
- Never auto-cleaned
- Agents can grep artifacts directly
- Important outputs are copied to `fs/` when needed

### 7. Deletions

- Delete `migrate run`
- Delete `export space`
- Delete `skills reindex`
- Delete `run retry`
- Delete `fs read/write/ls`
- Delete `context list`
- Delete `context pin/unpin`

### 8. Resilience

- JSONL self-healing readers: truncated trailing lines silently skipped
- Schema versioning: `"v": 1` in JSONL events, `"schema_version": 1` in space.json
- Doctor scope: stale session locks, orphan runs (synthetic finalize), stale space status, and missing/corrupt `space.json` detection (report + skip, no recreate)
- Security model: cooperative trust (documented limitation)
- `sessions.jsonl` stores `harness_session_id`, `harness`, `model`, and original passthrough `params` for session resumption/continuation defaults

## Out of Scope

- Compatibility/migration layers for old SQLite workflows
- Migration of existing `w`-prefixed spaces — clean break
- Additional fs convenience commands (`cat/cp/mv/rm/mkdir`)
- Cross-space index/query service
- Automatic run artifact retention/compaction
- Full Codex/OpenCode E2E parity work
- New inter-agent protocol beyond shared `fs/`
- Multi-space orchestration from within a harness (possible via shell, not explicitly supported)
- CLI REPL for multi-session management (deferred to V2 web UI)
- NFS/distributed filesystem support (local filesystem only)
- `fs read/write/ls` — agents use `$MERIDIAN_SPACE_FS/` directly
- `context list` — agent has `MERIDIAN_SPACE_ID` from env
- Context pin/unpin — agents manage context explicitly
- `run retry` — users manually retry with `run spawn`
- `space.json.description`, `space.json.labels` — no current consumer
- Adversarial agent security model — cooperative trust for MVP
- Launcher CLI/PTY split — premature for MVP

## Acceptance Criteria

1. No SQLite imports/usages remain in runtime paths.
2. All space/run/session state is represented by files in `.meridian/.spaces/<id>/`.
3. `MERIDIAN_SPACE_ID`, `MERIDIAN_SPACE_FS`, `MERIDIAN_SESSION_ID`, and `MERIDIAN_HARNESS_COMMAND` are provided to harness processes.
4. `fs/` is the only committed part of a space.
5. Deleted commands are absent from CLI/ops registry.
6. Session concurrency and liveness are file-lock based, with cleanup behavior implemented.
7. MCP server (`server/main.py`) registers only agent-mode commands (11 tools).
8. `meridian -h` with `MERIDIAN_SPACE_ID` shows only agent-relevant commands (`run`, `skills`, `models`, `doctor`) with JSON output default.
9. `doctor` is a standalone command that auto-repairs (stale session locks, orphan runs, stale status), reports missing/corrupt `space.json`, and skips those spaces (no recreate).
10. No `supervisor` terminology in codebase — uses `primary` (agent) and `harness` (process).
11. Space status is `active` or `closed` only.
12. `space.json` uses atomic writes, per-space locking, and `schema_version: 1`.
13. Auto-create space works for both CLI and MCP `run spawn` paths.
14. `sessions.jsonl` stores `harness_session_id`, `harness`, `model`, and original passthrough `params` for session resumption.
15. JSONL readers self-heal truncated trailing lines.
16. All JSONL events include `"v": 1`.
17. Error messages follow `[CODE] + cause + next action` format.
18. `meridian start` supports default auto-resume, `--new`, `--continue` (last chat), `--continue <chat-id|harness-session-id>` cross-space lookup, and optional `--space` disambiguation.
