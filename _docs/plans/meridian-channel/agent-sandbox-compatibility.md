# Agent Sandbox Compatibility

**Status:** done
**Reviewed:** 2026-02-26 (3 codex reviews + 1 sonnet explore)

## Problem

When meridian spawns agents via harness CLIs (codex, claude, opencode), several assumptions break inside sandboxed environments. Testing with `codex exec --sandbox read-only` and `workspace-write` revealed a chain of failures that prevent agents from using meridian as a tool or producing reports.

## Bugs Found

### Bug 1: `--dry-run` opens StateDB (write required)

**Severity:** P0
**File:** `src/meridian/lib/ops/run.py:352`
**Confirmed:** runtime probe — `PermissionError` in read-only sandbox

`_build_create_payload()` calls `build_runtime()` unconditionally, which opens `StateDB` with `PRAGMA journal_mode = WAL` — a write operation. Dry-run only needs the harness registry and prompt composition, not state.

**Error:**
```
sqlite3.OperationalError: attempt to write a readonly database
```

**Fix:** Lazy-init `StateDB`. Dry-run path should skip state entirely — only needs harness registry, skill loader, and prompt composer.

---

### Bug 2: `resolve_repo_root()` escapes workspace boundary

**Severity:** P0
**File:** `src/meridian/lib/config/_paths.py:27-29`
**Confirmed:** runtime probe — CWD `meridian-channel/` resolves to parent `meridian-collab`

`resolve_repo_root()` walks up from cwd looking for `.agents/skills/`. In submodule setups (e.g., `meridian-channel` inside `meridian-collab`), it resolves to the **parent monorepo**, placing `.meridian/index/runs.db` outside the codex workspace boundary.

**Impact:** Even `workspace-write` sandbox fails because the state db is outside the allowed write path. The codex workspace is `meridian-channel/` but the db is at `meridian-collab/.meridian/index/runs.db`.

**Fix options:**
1. `MERIDIAN_REPO_ROOT` env var (already supported, just not set by default in spawned agents)
2. Separate state root from repo root — state path doesn't need to follow `.agents/skills/` anchor
3. `--add-dir` on codex to grant write to parent `.meridian/` (workaround, not a fix)

---

### Bug 3: Report prompt assumes filesystem write access

**Severity:** P1
**File:** `src/meridian/lib/prompt/compose.py:21-35`

The prompt tells agents: *"As your FINAL action, write a report of your work to: `report.md`"*. Read-only agents can't write files, so the report never gets created.

**Current fallback:** `src/meridian/lib/extract/report.py` extracts the last assistant message from `output.jsonl` as a synthetic report. This works but the prompt is misleading — the agent wastes tokens trying (and failing) to write a file.

**Fix:** Change prompt instruction to: *"Your final message should be a report of your work."* Meridian captures stdout already. The report comes from the last message, not a file write. If the agent also wrote `report.md` (write-capable sandbox), prefer that.

**Harness-specific enhancement (codex only):** Codex supports `-o <path>` to write last assistant message to a file, bypassing sandbox. Could add this to codex command builder for read-only tiers, but the universal stdout approach is better.

---

### Bug 4: `meridian` not in PATH inside codex sandbox

**Severity:** P2 (expected behavior)
**Discovery:** Codex runs commands via `/bin/bash -lc` which doesn't activate the Python venv.

**Impact:** Agents can't run `meridian` by name. Must use absolute path: `.venv/bin/meridian`.

**Fix:** Not needed if using MCP (see below). For CLI usage, inject `PATH` override in env when spawning, or document that agents should use the MCP server.

---

### Bug 5: No cost tracking in run results

**Severity:** P2
**Discovery:** All runs in `run_list` show `cost_usd: null`.

**Not a sandbox bug** — just noticed during testing. Usage extraction may not be wired for all harnesses.

---

### Bug 6: Workspace launch skips permission enforcement when profile sandbox missing

**Severity:** P0
**File:** `src/meridian/lib/workspace/launch.py`
**Source:** codex review (2026-02-26)

When an agent profile has no `sandbox` field or an unknown value, `_permission_tier_from_profile()` returns `None`. The workspace launch path only appends permission flags when the inferred tier is not `None` — there is **no fallback to `config.default_permission_tier`**. This means a missing `sandbox` field silently spawns with no permission constraints.

**Fix:** Fall back to `config.default_permission_tier` when profile inference returns `None`.

---

### Bug 7: `sandbox` field never validated at parse time

**Severity:** P1
**File:** `src/meridian/lib/config/agent.py:64-74`
**Source:** both reviewers (2026-02-26)

`parse_agent_profile()` stores the raw `sandbox` string without validating against known values. A typo like `sandbox: full_access` (underscore) passes parsing silently, then `_permission_tier_from_profile()` returns `None`, falling through to default behavior with no warning.

**Fix:** Validate `sandbox` at parse time against known values (`read-only`, `workspace-write`, `danger-full-access`, `unrestricted`). Emit a warning for unknown values.

---

### Bug 8: OpenCode `DANGER` tier is a silent no-op

**Severity:** P1
**File:** `src/meridian/lib/safety/permissions.py`
**Source:** both reviewers (2026-02-26)

OpenCode `DANGER` tier produces `{"*":"allow"}` — identical to `FULL_ACCESS`. A warning is logged but there is no actual behavioral difference. Unlike Claude (`--dangerously-skip-permissions`) and Codex (`--dangerously-bypass-approvals-and-sandbox`), OpenCode has no equivalent bypass flag.

**Impact:** Callers using `DANGER` tier on OpenCode get `FULL_ACCESS` semantics silently. This is architecturally honest (OpenCode lacks the flag) but should be documented and surfaced as a warning at config validation time, not buried in runtime logs.

---

### Bug 9: `_permission_tier_from_profile()` duplicated in two files

**Severity:** P2
**Files:** `src/meridian/lib/ops/run.py:355-388`, `src/meridian/lib/workspace/launch.py:233-266`
**Source:** both reviewers (2026-02-26)

Identical implementations of `_permission_tier_from_profile()`, `_warn_profile_tier_escalation()`, and `_TIER_RANKS` exist in both files. Drift risk — a fix in one file can be missed in the other.

**Fix:** Consolidate into `src/meridian/lib/safety/permissions.py` and import from both call sites.

---

### Bug 10: Workspace supervisor hardcodes `HarnessId("claude")`

**Severity:** P1
**File:** `src/meridian/lib/workspace/launch.py` (`_build_interactive_command()`)
**Source:** both reviewers (2026-02-26)

Permission flags are always computed with `permission_flags_for_harness(HarnessId("claude"), ...)`, regardless of the supervisor's actual model/harness. Currently the supervisor IS always Claude-based, but this hardcoding means changing the supervisor model produces mismatched harness/permission flags silently.

**Fix:** Resolve the harness from the supervisor's model (same routing logic as `ops/run.py`) and use it for permission flag generation.

---

### Bug 11: `_permission_config_for_env_overrides` duck-typing fallback

**Severity:** P1
**File:** `src/meridian/lib/exec/spawn.py`
**Source:** sonnet review (2026-02-26)

Extracting the config from the resolver uses `getattr(resolver, "config", None)`. If a custom `PermissionResolver` lacks `.config`, OpenCode silently gets `PermissionConfig()` (read-only defaults) for its env var, regardless of what `resolve_flags()` actually returns. The CLI-flag path and env-var path can disagree.

**Fix:** Add `config` as a required property on the `PermissionResolver` Protocol, or pass `PermissionConfig` explicitly alongside the resolver.

---

### Bug 12: Exec cleanup targets only direct child process

**Severity:** P1
**File:** `src/meridian/lib/exec/spawn.py`
**Source:** codex review (2026-02-26)

Timeouts, signals, and cancellation terminate only the direct child process. Grandchildren (e.g., a harness spawning sub-processes) can survive and hold pipes/resources in CI/container contexts.

**Fix:** Use process groups (`os.setpgrp` / `os.killpg`) to ensure the entire process tree is cleaned up on timeout/signal.

---

### Bug 13: `SignalForwarder` is process-global, not concurrent-safe

**Severity:** P1
**File:** `src/meridian/lib/exec/signals.py`
**Source:** codex review (2026-02-26)

`SignalForwarder` installs global `SIGINT`/`SIGTERM` handlers. Overlapping background runs (e.g., parallel fan-out) can clobber each other's handlers.

**Impact:** In single-run CLI mode this is fine. In concurrent workspace/supervisor scenarios, last-registered handler wins and other runs lose signal forwarding.

**Fix:** Use a signal demux — single global handler that dispatches to all active `SignalForwarder` instances.

---

### Bug 14: Full parent environment inherited by child runs

**Severity:** P1
**File:** `src/meridian/lib/exec/spawn.py`
**Source:** codex review (2026-02-26)

Child processes inherit the full parent environment via `os.environ.copy()`. In CI/container contexts, this exposes secrets (API keys, tokens, credentials) that the child agent does not need.

**Fix:** Sanitize the environment before spawning — only pass known-safe variables plus explicit `env_overrides`. Or at minimum, redact known secret patterns (`*_TOKEN`, `*_KEY`, `*_SECRET`) from the inherited env.

---

### Bug 15: CLI exit code masks run failures

**Severity:** P1
**File:** `src/meridian/cli/run.py`
**Source:** codex direct CLI test (2026-02-26)
**Confirmed:** `run create -p 'Say hello' --model claude-haiku-4-5` returns shell exit `0` even when the run result is `failed` with `exit=1`.

**Impact:** Automation and CI scripts that check `$?` will incorrectly treat failed runs as successful. Agents using meridian CLI (vs MCP) cannot distinguish success from failure.

**Fix:** `run create` should propagate the run's exit code as the CLI exit code. Exit `0` only when the run succeeds.

---

### Bug 16: Unhandled exceptions leak Python tracebacks

**Severity:** P1
**Files:** `src/meridian/cli/run.py`, `src/meridian/cli/skills_cmd.py`, `src/meridian/cli/models_cmd.py`
**Source:** codex direct CLI test (2026-02-26)
**Confirmed:** `skills show <unknown>`, `run show <unknown>`, `workspace show <unknown>`, `models show <unknown>` all crash with raw Python tracebacks.

**Impact:** User-facing CLI should never show raw tracebacks. In sandboxed agent contexts, tracebacks waste tokens and confuse the agent.

**Fix:** Add a top-level exception handler in the CLI entry point that catches `KeyError`, `ValueError`, and `FileNotFoundError` from operations and emits a clean error message with non-zero exit code.

---

### Bug 17: Empty prompt accepted by `run create`

**Severity:** P2
**File:** `src/meridian/lib/ops/run.py`
**Source:** codex direct CLI test (2026-02-26)
**Confirmed:** `run create` with no `-p` flag creates and executes a run with an empty prompt, which succeeds.

**Impact:** Wastes agent API tokens on a no-op run. Agents calling meridian programmatically can accidentally create empty runs.

**Fix:** Validate that `prompt` is non-empty in `run_create_sync()` and return an error immediately.

---

### Bug 18: Invalid model names not rejected upfront

**Severity:** P2
**File:** `src/meridian/lib/ops/run.py`
**Source:** codex direct CLI test (2026-02-26)
**Confirmed:** `run create -p 'test' --model not-a-model` warns and falls back to codex harness, then retries 3 times before failing.

**Impact:** Wastes time and tokens on retries for a fundamentally unrecoverable input error. Should fail fast.

**Fix:** Validate the model against the catalog in `run_create_sync()` before building the runtime. Return a clear error for unknown models.

---

### Bug 19: `config show` with nonexistent `MERIDIAN_REPO_ROOT` succeeds misleadingly

**Severity:** P2
**File:** `src/meridian/lib/ops/config.py`
**Source:** codex direct CLI test (2026-02-26)
**Confirmed:** `MERIDIAN_REPO_ROOT=/does/not/exist meridian config show` prints config at that path without error, but later operations crash with `PermissionError` trying to create state directories.

**Impact:** Misleading UX — user thinks config is valid, then gets an unrelated crash. In sandbox contexts, the agent may trust the config output and proceed incorrectly.

**Fix:** `config show` should warn (not crash) when the resolved root doesn't exist on disk.

---

### Bug 20: `SkillRegistry` also opens SQLite with WAL on init — dry-run fix incomplete

**Severity:** P0
**File:** `src/meridian/lib/config/skill_registry.py:66, 80-90`
**Source:** codex deep review (2026-02-26)

`SkillRegistry.__init__` calls `_ensure_schema()` which opens SQLite with `PRAGMA journal_mode = WAL`. Even if Slice 1 skips `build_runtime()` / `StateDB` for dry-run, the `SkillRegistry` instantiation in `_build_create_payload()` (`ops/run.py:426-433`) still triggers a write.

**Impact:** Slice 1's proposed fix is insufficient — dry-run will still fail in read-only sandboxes.

**Fix:** Introduce a read-only/filesystem-only skill loading path for dry-run. `SkillRegistry` should support a no-index mode that scans `.agents/skills/` without opening SQLite.

---

### Bug 21: Workspace launch has same `SkillRegistry` write-through

**Severity:** P1
**File:** `src/meridian/lib/workspace/launch.py:158-166`
**Source:** codex deep review (2026-02-26)

`_build_interactive_command()` creates `SkillRegistry` and may call `reindex()`, triggering the same WAL write as Bug 20 in the workspace supervisor launch path.

**Fix:** Mirror Bug 20 fix — use no-index skill loading path when appropriate.

---

### Bug 22: Hardcoded `.meridian` paths scattered across 5+ files

**Severity:** P0
**File:** Multiple: `ops/run.py:524,571,650`, `_runtime.py:65`, `exec/spawn.py:87-94`, `workspace/launch.py:312`
**Source:** codex deep review (2026-02-26)

Slice 4's `MERIDIAN_STATE_ROOT` proposal is incomplete because `.meridian` paths are hardcoded in many files beyond `_paths.py`. Without centralizing state path resolution first, the env var will only fix some codepaths.

**Fix:** Create a centralized state path provider (in `config/_paths.py` or new `state/paths.py`) consumed by all callsites before implementing Slice 4.

---

### Bug 23: Workspace command is fully hardcoded to Claude CLI, not just permission flags

**Severity:** P1
**File:** `src/meridian/lib/workspace/launch.py:186-192`
**Source:** codex deep review (2026-02-26)

Slice 6 proposes routing only permission flags by harness, but `_build_interactive_command()` always emits `claude --system-prompt ...` as the base command. Non-Claude supervisor models would execute through the Claude CLI with incompatible flags/model IDs.

**Fix:** Either enforce Claude-only supervisor with early validation (pragmatic), or implement full harness-specific workspace command builders (extensible).

---

### Bug 24: Claude `--allowedTools` collision between MCP filtering and permissions

**Severity:** P1
**File:** `src/meridian/lib/safety/permissions.py:167`, `src/meridian/lib/harness/_strategies.py:98`
**Source:** codex deep review (2026-02-26)

Both the permission system and the proposed MCP tool filtering (Slice 3) emit `--allowedTools` for Claude. The command builder appends permission flags in a fixed slot. Last-write-wins behavior can silently fail-open or fail-closed.

**Fix:** Define merge semantics for Claude allowed tools (union for MCP + permissions, intersection for restrictions). Emit one consolidated `--allowedTools` value.

---

### Bug 25: Signal race extends beyond `SignalForwarder` into finalize SIGTERM masking

**Severity:** P1
**File:** `src/meridian/lib/exec/spawn.py:643-657`
**Source:** codex deep review (2026-02-26)

The finalize path in `spawn.py` mutates the process-global SIGTERM handler per run. Bug 13 / Slice 7 only addresses `SignalForwarder` in `signals.py`. Concurrent runs can still clobber each other's SIGTERM behavior during finalize persistence.

**Fix:** Unify ALL signal mutation behind one global coordinator, including both `SignalForwarder` and finalize atomic-write windows.

---

### Bug 26: No MCP server crash/reconnect strategy

**Severity:** P1
**File:** `src/meridian/lib/harness/adapter.py:74-91`
**Source:** codex deep review (2026-02-26)

The harness adapter protocol has no MCP lifecycle hooks or health channel. Slice 3 wires MCP startup but doesn't handle mid-run MCP sidecar crashes. The agent gets opaque harness errors with no recovery path.

**Fix:** Add error classification for MCP transport failures. Document expected behavior (harness retries vs immediate fail). Consider health-check or reconnect policy.

---

### Bug 27: `mcp-tools` values unvalidated against registered operations

**Severity:** P1
**File:** `src/meridian/lib/config/agent.py:73, 38-50`
**Source:** codex deep review (2026-02-26)

`mcp-tools` in agent profiles are parsed as arbitrary strings with no validation against the MCP server's actual tool registry. Typos silently produce either zero-tool or over-broad behavior.

**Fix:** Validate `mcp-tools` against the operation registry (`mcp_name` set from `server/main.py`) at profile load time. Normalize casing/duplicates.

---

### Bug 28: StateDB lock/corruption errors bubble as raw failures

**Severity:** P1
**File:** `src/meridian/lib/state/db.py:49-53`, `src/meridian/lib/ops/run.py:523-554, 646-669`
**Source:** codex deep review (2026-02-26)

`StateDB` connection setup applies WAL/migrations directly. Callers don't catch `sqlite3.OperationalError` for lock contention or corruption. Errors bubble as raw failures that break agent control loops.

**Fix:** Introduce classified DB exceptions + consistent user-facing errors + optional retry/backoff for lock contention (`database is locked`).

---

### Bug 29: Orphan-lock cleanup vulnerable to PID reuse

**Severity:** P2
**File:** `src/meridian/lib/workspace/launch.py:269-281, 336-337`
**Source:** codex deep review (2026-02-26)

Liveness check uses `os.kill(pid, 0)` only. A reused PID from an unrelated process can preserve a stale lock, blocking workspace operations.

**Fix:** Include parent PID, started_at timestamp, or command fingerprint when validating lock ownership.

---

## MCP Server: The Right Path

### Current state

`meridian serve` is a fully functional FastMCP stdio server. It auto-registers all operations as MCP tools (22 tools total). Tested and working:

```bash
# Register with codex
codex mcp add meridian -- uv run --directory /path/to/meridian-channel meridian serve

# Codex in read-only successfully calls meridian tools via MCP
codex exec --model gpt-5.3-codex-spark --sandbox read-only \
  "Use the run_list tool to list recent runs"
# → Works! Returns full run history via MCP, no filesystem access needed.
```

### Why MCP solves the sandbox problem

The MCP server runs **outside** the sandbox (as a sidecar process started by the harness). The agent sends tool requests over stdio. No filesystem writes needed from the agent side.

```
┌─────────────────────────────┐
│  codex sandbox (read-only)  │
│                             │
│  agent ──MCP stdio──┐      │
│                     │      │
└─────────────────────┼──────┘
                      │
              ┌───────▼───────┐
              │ meridian serve│  ← runs outside sandbox
              │ (FastMCP)     │  ← has full write access
              │               │
              │ StateDB ──────┼── .meridian/index/runs.db
              │ ArtifactStore ┼── .meridian/artifacts/
              └───────────────┘
```

### Tool filtering by agent role

All three harnesses support MCP tool filtering:

| Harness | Mechanism |
|---------|-----------|
| Codex | `enabled_tools` in `[mcp_servers.meridian]` config |
| Claude | `--allowedTools "mcp__meridian__run_list"` (supports `mcp__meridian__*` wildcard) |
| OpenCode | glob patterns in permissions config |

**Proposed role-based tool sets:**

| Role | Allowed MCP tools |
|------|-------------------|
| reviewer | `run_list`, `run_show`, `skills_list`, `skills_search`, `models_list` |
| coder | All reviewer tools + `run_create`, `context_pin`, `context_list` |
| supervisor | All tools |

Driven by agent profile frontmatter (alongside existing `tools`, `sandbox`, `skills`):
```yaml
---
name: reviewer
sandbox: read-only
mcp-tools: [run_list, run_show, skills_list, skills_search, models_list]
---
```

No config system dependency — agent profiles are the single source of truth for agent capabilities.

## Proposed Slices

### Slice 0: State path abstraction unification (P0 foundation)
**Bugs addressed:** 22 (prerequisite for 1, 2, 4)
- Create centralized state path provider in `config/_paths.py` (or new `state/paths.py`)
- Replace ALL hardcoded `.meridian` path constructions:
  - `ops/run.py:524, 571, 650`
  - `_runtime.py:65`
  - `exec/spawn.py:87-94`
  - `workspace/launch.py:312`
- Single function: `resolve_state_root(repo_root) -> Path` — consumed everywhere
- Support `MERIDIAN_STATE_ROOT` env var override (distinct from `MERIDIAN_REPO_ROOT`)
- Test: all state paths flow through centralized provider
- Test: `MERIDIAN_STATE_ROOT` override is respected by all callsites

### Slice 1a: Dry-run no-write path (P0)
**Bugs addressed:** 1, 20, 21
**Depends on:** Slice 0
- Make `_build_create_payload()` skip `build_runtime()` AND `SkillRegistry` index init when `dry_run=True`
- Introduce `SkillRegistry` no-index mode: filesystem scan of `.agents/skills/` without opening SQLite
- Mirror in workspace launch path (Bug 21)
- Test: `meridian run create --dry-run -p "test"` works without `.meridian/` existing
- Test: `SkillRegistry(index=False)` loads skills from disk without SQLite
- Test: workspace dry-run/skill-loading path doesn't write

### Slice 1b: Permission fallback when profile sandbox missing (P0)
**Bugs addressed:** 6
- Fix workspace launch to fall back to `config.default_permission_tier` when `_permission_tier_from_profile()` returns `None`
- Test: workspace launch with missing `sandbox` field uses default tier
- Test: workspace launch with unknown `sandbox` value uses default tier with warning

### Slice 2: Report from last message (universal)
**Bugs addressed:** 3
- Change prompt instruction from "write a report file" to "your final message should be a report"
- Update prompt sanitization and related tests atomically (tests assert current wording)
- Ensure extraction from last assistant message is the primary path
- Keep file-based report as an enhancement when available (agent wrote `report.md`)
- Test: read-only agent produces a report via stdout capture

### Slice 3a: Agent profile validation (`sandbox` + `mcp-tools`)
**Bugs addressed:** 7, 27
- Validate `sandbox` at parse time against known values; warn on unknown
- Validate `mcp-tools` against MCP operation registry (`mcp_name` set); warn on unknown tool names
- Normalize casing/duplicates in `mcp-tools`
- Test: unknown `sandbox` value emits warning
- Test: typo in `mcp-tools` emits warning at load time

### Slice 3b: MCP transport wiring through adapter extension points
**Bugs addressed:** (new capability), 24, 26
**Depends on:** Slice 3a
- Add MCP config builder as adapter-level extension point (not harness `if` branches in `ops/run.py`)
- Codex: `--config mcp_servers.meridian.command=["uv","run","meridian","serve"]`
- Claude: `--mcp-config` with meridian server definition
- Define merge semantics for Claude `--allowedTools` (MCP tools + permission tools → one consolidated value)
- Filter tools based on agent profile `mcp-tools` field
- Document MCP crash behavior per harness (reconnect policy)
- Test: codex agent in read-only can call `run_list` via MCP
- Test: Claude `--allowedTools` correctly merges permission and MCP tool lists

### Slice 4: Repo root boundary fix
**Bugs addressed:** 2
**Depends on:** Slice 0
- `resolve_repo_root()` respects workspace boundaries (stop at submodule root)
- Inject `MERIDIAN_REPO_ROOT` and `MERIDIAN_STATE_ROOT` when spawning child agents
- Test: meridian works inside submodule workspace without escaping to parent
- Test: spawned child agents inherit correct env vars

### Slice 5: Permission helper consolidation
**Bugs addressed:** 8, 9, 11
- Consolidate `_permission_tier_from_profile()` + `_warn_profile_tier_escalation()` + `_TIER_RANKS` into `safety/permissions.py`
- Keep `PermissionResolver` Protocol minimal (ISP) — pass `PermissionConfig` explicitly where env overrides need it, don't add `.config` to the protocol
- Document OpenCode `DANGER` tier limitation; surface warning at config validation
- Test: all permission helpers imported from single source
- Test: `DANGER` on OpenCode logs clear limitation message
- Test: existing `PermissionResolver` test doubles still work unchanged

### Slice 6: Workspace launch harness strategy
**Bugs addressed:** 10, 23
**Depends on:** Slice 5
- **Pragmatic approach:** Enforce Claude-only supervisor model with early validation (current reality)
- Route permission flags through resolved harness (not hardcoded `HarnessId("claude")`)
- Add validation: if supervisor model resolves to non-Claude harness, raise clear error
- Future: full harness-specific workspace command builders (out of scope for this plan)
- Test: Claude supervisor produces correct permission flags
- Test: non-Claude supervisor model raises clear error (not silent mismatch)

### Slice 7a: Process-group cleanup
**Bugs addressed:** 12
- Use `os.setpgrp` / `os.killpg` for full process tree cleanup on timeout/signal/cancel
- Test timeout + signal + cleanup triple overlap (the interaction edge case)
- Test: grandchild processes are cleaned up on timeout

### Slice 7b: Global signal coordinator
**Bugs addressed:** 13, 25
- Implement signal demux — single global handler dispatching to ALL signal-mutating code:
  - `SignalForwarder` instances in `signals.py`
  - Finalize SIGTERM masking in `spawn.py:643-657`
- Test: concurrent runs don't clobber signal handlers
- Test: finalize persistence is not interrupted by concurrent signal registration

### Slice 7c: Environment propagation policy
**Bugs addressed:** 14
- Define allowlist of known-safe env vars to pass to child processes
- Explicit pass-through for required harness credentials (API keys the agent DOES need)
- Redact known secret patterns (`*_TOKEN`, `*_KEY`, `*_SECRET`) unless in pass-through list
- Test: secret env vars are not passed to child processes
- Test: required harness credentials (e.g., `ANTHROPIC_API_KEY`) ARE passed

### Slice 8: CLI robustness + input validation
**Bugs addressed:** 15, 16, 17, 18, 19, 28
- Propagate run exit code as CLI exit code in `run create` (bug 15)
- Add top-level exception handler — emit clean error messages, no tracebacks (bug 16)
- Validate non-empty prompt in `run_create_sync()` (bug 17)
- Validate model against catalog before building runtime; distinguish "unknown alias" vs "non-catalog harness-allowed model" (bug 18)
- Warn in `config show` when resolved repo root doesn't exist on disk (bug 19)
- Classify StateDB exceptions: lock contention → retry, corruption → user-facing error (bug 28)
- Test: `run create` with failed run exits non-zero
- Test: `run show <unknown>` prints error message, not traceback
- Test: `run create` with empty prompt returns error
- Test: `run create --model not-a-model` fails fast with clear message
- Test: `database is locked` → graceful retry, not crash

### Deferred (out of scope)
**Bugs noted but not sliced:**
- Bug 29 (PID reuse in orphan-lock cleanup) — P2, low risk, can fix opportunistically
- Bug 5 (cost tracking) — not a sandbox bug
- Bug 4 (PATH in codex sandbox) — not needed with MCP approach

## Slice Dependency Graph

```
Slice 0 (state path abstraction)      ── no deps, FOUNDATION
  ├── Slice 1a (dry-run no-write)     ── after Slice 0
  ├── Slice 4  (repo root boundary)   ── after Slice 0
  │
Slice 1b (permission fallback)         ── no deps
Slice 2  (report from last message)    ── no deps
Slice 3a (profile validation)          ── no deps
  └── Slice 3b (MCP transport wiring)  ── after Slice 3a
Slice 5  (permission consolidation)    ── no deps
  └── Slice 6  (workspace harness)     ── after Slice 5
Slice 7a (process-group cleanup)       ── no deps
Slice 7b (global signal coordinator)   ── no deps
Slice 7c (env propagation policy)      ── no deps
Slice 8  (CLI robustness)              ── no deps
```

**Phase 1 (parallel):** Slices 0, 1b, 2, 3a, 5, 7a, 7b, 7c, 8
**Phase 2 (after deps):** Slices 1a (after 0), 3b (after 3a), 4 (after 0), 6 (after 5)

## Dependencies

- **Slice 0 is the foundation** — Slices 1a and 4 cannot start until state path abstraction is in place
- **Run output streaming** — already implemented; report extraction (Slice 2) builds on that work
- **Agent profiles** — `mcp-tools` field extends existing frontmatter schema (`src/meridian/lib/config/agent.py`)
- **PermissionResolver Protocol** — Slice 5 must NOT broaden it (ISP); pass `PermissionConfig` explicitly instead

## Test matrix

### Manual session (initial discovery)

| Test | Sandbox | Result |
|------|---------|--------|
| `codex exec "2+2"` | read-only | Pass |
| `meridian --version` (absolute path) | read-only | Pass |
| `meridian run --help` | read-only | Pass |
| Write file to disk | read-only | Blocked (expected) |
| Write file to disk | workspace-write | Pass |
| Write to `.meridian/` | workspace-write | Pass |
| `meridian run create --dry-run` | read-only | **Fail** (WAL pragma) |
| `meridian run create --dry-run` | workspace-write | **Fail** (repo root escapes) |
| SQLite WAL pragma directly | workspace-write | Pass |
| `run_list` via MCP | read-only | **Pass** |
| codex `-o` flag | read-only | Pass (bypasses sandbox) |

### Codex sandbox e2e tests (2026-02-26)

| Test | Sandbox | Result | Bugs |
|------|---------|--------|------|
| `meridian --version` | read-only | Pass | — |
| `meridian run --help` | read-only | Pass | — |
| `meridian models list` | read-only | Pass | — |
| `meridian run create --dry-run` | read-only | **Fail** (`sqlite3.OperationalError`) | 1 |
| `run_list` via MCP | read-only | **Pass** | — |
| `models_list` via MCP | read-only | **Pass** | — |
| `meridian run create --dry-run` | workspace-write | **Fail** (WAL — DB outside workspace) | 1, 2 |
| `meridian run list` | workspace-write | **Fail** (WAL — DB outside workspace) | 2 |
| `resolve_repo_root()` | workspace-write | Returns parent monorepo | 2 |
| Write to `/tmp` and cwd | read-only | Both denied (`Permission denied`) | 3 |

### Direct CLI exercise (2026-02-26, codex)

| Test | Result | Bugs |
|------|--------|------|
| All top-level commands (`--help`, `--version`, `models list`, etc.) | Pass | — |
| `run create --dry-run` in clean tmpdir with `MERIDIAN_REPO_ROOT` | Pass | — |
| `run create --dry-run` with read-only `.meridian/` | **Fail** (WAL pragma) | 1 |
| `resolve_repo_root()` from submodule | Returns parent | 2 |
| `run create -p 'hello' --model claude-haiku-4-5` (run fails internally) | CLI exits `0` | 15 |
| `skills show <unknown>` | Raw traceback | 16 |
| `run show <unknown>` | Raw traceback | 16 |
| `workspace show <unknown>` | Raw traceback | 16 |
| `models show <unknown>` | Raw traceback | 16 |
| `run create` with no prompt | Creates empty run (succeeds) | 17 |
| `run create --model not-a-model` | Warns, falls back, retries 3x | 18 |
| `config show` with `MERIDIAN_REPO_ROOT=/does/not/exist` | Prints config, later ops crash | 19 |
| MCP `tools/list` (with proper init handshake) | 22 tools returned | — |
| Permission flags for all tier/harness combos | Correct mappings | 8 (OpenCode `[]`) |

## SOLID Compliance Notes

From the deep architectural review:

- **ISP**: `PermissionResolver` Protocol must stay minimal — `resolve_flags()` only. Pass `PermissionConfig` explicitly where env overrides need it (Slice 5).
- **OCP**: MCP wiring must go through adapter extension points, not `if harness ==` branches in `ops/run.py` (Slice 3b).
- **SRP**: Original Slice 1 bundled dry-run fix + permission fallback (unrelated concerns) — now split into 1a/1b. Original Slice 7 packed 3 subsystems — now split into 7a/7b/7c.
- **DIP**: State path resolution must be an abstraction consumed by callsites, not hardcoded string concatenation (Slice 0).
- **LSP**: Workspace launch must validate Claude-only invariant explicitly rather than silently producing wrong flags for other harnesses (Slice 6).

## Review History

| Date | Reviewer(s) | Findings |
|------|-------------|----------|
| 2026-02-26 | `gpt-5.3-codex` (reviewer), `claude-sonnet-4-6` (explore) | Bugs 6–14 added; slices expanded from 4 → 7; runtime probes confirmed bugs 1–2 |
| 2026-02-26 | `gpt-5.3-codex` (sandbox e2e), `gpt-5.3-codex` (direct CLI) | Bugs 1–2 confirmed in real sandboxes; bugs 15–19 discovered; slice 8 added |
| 2026-02-26 | `gpt-5.3-codex` (deep architectural review) | Bugs 20–29 added; SOLID violations identified; slices restructured from 8 → 13 (0, 1a, 1b, 2, 3a, 3b, 4, 5, 6, 7a, 7b, 7c, 8); dependency graph corrected |
