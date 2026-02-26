# Agent Sandbox Compatibility

**Status:** draft

## Problem

When meridian spawns agents via harness CLIs (codex, claude, opencode), several assumptions break inside sandboxed environments. Testing with `codex exec --sandbox read-only` and `workspace-write` revealed a chain of failures that prevent agents from using meridian as a tool or producing reports.

## Bugs Found

### Bug 1: `--dry-run` opens StateDB (write required)

**Severity:** high
**File:** `src/meridian/lib/ops/run.py:352`

`_build_create_payload()` calls `build_runtime()` unconditionally, which opens `StateDB` with `PRAGMA journal_mode = WAL` — a write operation. Dry-run only needs the harness registry and prompt composition, not state.

**Error:**
```
sqlite3.OperationalError: attempt to write a readonly database
```

**Fix:** Lazy-init `StateDB`. Dry-run path should skip state entirely — only needs harness registry, skill loader, and prompt composer.

---

### Bug 2: `resolve_repo_root()` escapes workspace boundary

**Severity:** high
**File:** `src/meridian/lib/config/_paths.py:27-29`

`resolve_repo_root()` walks up from cwd looking for `.agents/skills/`. In submodule setups (e.g., `meridian-channel` inside `meridian-collab`), it resolves to the **parent monorepo**, placing `.meridian/index/runs.db` outside the codex workspace boundary.

**Impact:** Even `workspace-write` sandbox fails because the state db is outside the allowed write path. The codex workspace is `meridian-channel/` but the db is at `meridian-collab/.meridian/index/runs.db`.

**Fix options:**
1. `MERIDIAN_REPO_ROOT` env var (already supported, just not set by default in spawned agents)
2. Separate state root from repo root — state path doesn't need to follow `.agents/skills/` anchor
3. `--add-dir` on codex to grant write to parent `.meridian/` (workaround, not a fix)

---

### Bug 3: Report prompt assumes filesystem write access

**Severity:** medium
**File:** `src/meridian/lib/prompt/compose.py:21-35`

The prompt tells agents: *"As your FINAL action, write a report of your work to: `report.md`"*. Read-only agents can't write files, so the report never gets created.

**Current fallback:** `src/meridian/lib/extract/report.py` extracts the last assistant message from `output.jsonl` as a synthetic report. This works but the prompt is misleading — the agent wastes tokens trying (and failing) to write a file.

**Fix:** Change prompt instruction to: *"Your final message should be a report of your work."* Meridian captures stdout already. The report comes from the last message, not a file write. If the agent also wrote `report.md` (write-capable sandbox), prefer that.

**Harness-specific enhancement (codex only):** Codex supports `-o <path>` to write last assistant message to a file, bypassing sandbox. Could add this to codex command builder for read-only tiers, but the universal stdout approach is better.

---

### Bug 4: `meridian` not in PATH inside codex sandbox

**Severity:** low (expected behavior)
**Discovery:** Codex runs commands via `/bin/bash -lc` which doesn't activate the Python venv.

**Impact:** Agents can't run `meridian` by name. Must use absolute path: `.venv/bin/meridian`.

**Fix:** Not needed if using MCP (see below). For CLI usage, inject `PATH` override in env when spawning, or document that agents should use the MCP server.

---

### Bug 5: No cost tracking in run results

**Severity:** low
**Discovery:** All runs in `run_list` show `cost_usd: null`.

**Not a sandbox bug** — just noticed during testing. Usage extraction may not be wired for all harnesses.

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

### Slice 1: Fix dry-run StateDB requirement
- Make `_build_create_payload()` skip `build_runtime()` when `dry_run=True`
- Extract harness registry, skill loader, prompt composer into a lightweight path
- Test: `meridian run create --dry-run -p "test"` works without `.meridian/` existing

### Slice 2: Report from last message (universal)
- Change prompt instruction from "write a report file" to "your final message should be a report"
- Ensure extraction fallback is the primary path, not the fallback
- Keep file-based report as an enhancement when available (agent wrote `report.md`)
- Test: read-only agent produces a report via stdout capture

### Slice 3: MCP server wiring for agent spawning
- When building harness commands, auto-configure MCP server connection
  - Codex: `--config mcp_servers.meridian.command=["uv","run","meridian","serve"]`
  - Claude: `--mcp-config` with meridian server definition
- Filter tools based on agent profile `mcp-tools` field
- Test: codex agent in read-only can call `run_list` via MCP

### Slice 4: Repo root boundary fix
- Add `MERIDIAN_STATE_ROOT` env var (distinct from `MERIDIAN_REPO_ROOT`)
- Or: separate state path resolution from skill/agent discovery
- Inject correct env vars when spawning child agents
- Test: meridian works inside submodule workspace without escaping to parent

## Dependencies

- **Run output streaming** — Slices 1-3 already implemented; report extraction (this plan Slice 2) builds on that work
- **Agent profiles** — `mcp-tools` field extends existing frontmatter schema (`src/meridian/lib/config/agent.py`)

## Test matrix (from session)

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
