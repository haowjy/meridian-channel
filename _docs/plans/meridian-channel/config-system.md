# Meridian Config System

**Status:** done

## Problem

Many operational values are hardcoded in Python that should be configurable per-repo. There is no central config mechanism — only `.meridian/models.toml` for model catalog overrides and scattered env vars.

## Design

Two systems, each handling a different concern:

### 1. Config file (`.meridian/config.toml`) — operational settings

CLI-managed via `meridian config` commands. Stores operational knobs that affect how meridian behaves. Config is purely operational — it does NOT define agent capabilities (that's agent profiles).

```toml
[defaults]
max_depth = 3
max_retries = 3
retry_backoff_seconds = 0.25

# Default agent profiles used when no --agent flag is provided.
# "supervisor" is used for `meridian workspace start` sessions.
# "agent" is used for `meridian run` (standalone or child runs).
supervisor_agent = "supervisor"
agent = "agent"

[timeouts]
kill_grace_seconds = 2.0
guardrail_seconds = 30.0
wait_seconds = 600.0

[permissions]
default_tier = "read-only"
# NOTE: danger tier MUST remain opt-in via --unsafe flag.
# Per-tier tool allowlists stay internal (security).

[search_paths]
# Directories to scan for agent profiles and skills.
# Meridian merges profiles/skills found across all paths (first match wins on name collision).
agents = [".agents/agents", ".claude/agents", ".opencode/agents", ".cursor/agents"]
skills = [".agents/skills", ".claude/skills", ".opencode/skills", ".cursor/skills"]
```

**What is NOT in config:**
- Harness commands — adapters own their CLI commands (`ClaudeAdapter`, `CodexAdapter`, `OpenCodeAdapter`). They build complex command lines with model routing, permission flags, etc. Exposing `[harness.*]` config would be misleading since custom flags need custom adapter logic.
- Agent capabilities — skills, sandbox, tools, mcp-tools belong in agent profiles (`.agents/agents/*.md`).
- Base skill injection — determined by agent profiles, not by skill metadata or config.

### 2. Models file (`.meridian/models.toml`) — model catalog

Already exists. Extend with:
- Alias mappings
- Role/cost metadata
- `harness` override stays as an escape hatch for unusual model IDs

The default model comes from the agent profile pointed to by `defaults.agent` or `defaults.supervisor_agent` in config.toml. The model catalog is purely for aliases, metadata, and harness overrides — no `default` flag.

### Agent profiles own capabilities

Agent profiles (`.agents/agents/*.md`) are the single source of truth for agent capabilities:

```yaml
---
name: supervisor
description: Workspace supervisor — decomposes tasks and manages child runs
model: claude-opus-4-6
skills: [run-agent, agent, orchestrate]
sandbox: unrestricted
mcp-tools: [run_create, run_list, run_show, run_wait, skills_list, models_list]
---
```

```yaml
---
name: agent
description: Default agent for standalone and child runs
model: gpt-5.3-codex
skills: [run-agent, agent]
sandbox: workspace-write
mcp-tools: [run_list, run_show, skills_list]
---
```

The config's `defaults.supervisor_agent` and `defaults.agent` point to these profiles by name. When no `--agent` flag is provided:
- `meridian workspace start` loads the profile named by `defaults.supervisor_agent` (fallback: hardcoded `"supervisor"`)
- `meridian run` loads the profile named by `defaults.agent` (fallback: hardcoded `"agent"`)
- If the named profile doesn't exist, fall back to current behavior (no profile, builtin defaults)

This eliminates `base_skills.py` entirely — there are no "base skills" as a concept. Each agent profile declares its own skills. The hardcoded base skill lists become the default skills in the default agent profiles.

### Agent profile decomposition into harness flags

**Principle:** Meridian owns the agent profile. Harnesses never receive `--agent` — they receive decomposed primitives (model, permissions, prompt with skills). This ensures consistent behavior across all three harnesses and avoids double injection of skills.

Each harness has different native mechanisms for the same concepts. Meridian's adapters translate agent profile fields into harness-specific flags:

#### Skills — prompt injection (universal)

All three harnesses support skills loaded from `.agents/skills/` on disk, but each has a different mechanism for per-agent skill selection:
- **Claude Code**: `--agent` profiles with `skills:` field — natively injects skill content
- **Codex**: no per-agent skill selection — loads skills from disk but no CLI flag to control which
- **OpenCode**: `--agent` profiles with agent config — but no native skill injection currently

**Problem with native skill loading:** If meridian passes `--agent reviewer` to Claude and the Claude agent profile has `skills: [reviewing]`, Claude injects the skill natively. But meridian also prompt-injects the same skill. Double injection.

**Problem with compaction:** All harnesses compact/summarize long conversations, which can lose skill context from the initial prompt. Meridian re-injects skills on `run continue` / `workspace resume`, but native skill injection doesn't survive compaction the same way.

**Solution:** Meridian always prompt-injects skills. Never pass `--agent` to any harness. The `FlagStrategy` for `agent` and `skills` is `DROP` on all three adapters. Skills are composed into the prompt text as `# Skill: <name>` sections by `compose_run_prompt_text()`.

**Deduplication:** When both `--agent reviewer` (profile has `skills: [reviewing]`) and `--skills reviewing,implementing` are provided, the final skill list is `unique(agent_profile.skills + explicit_skills)` — no skill is injected twice. This is already handled by `dedupe_skill_names()` in `assembly.py`.

**Why prompt injection over native skill loading:** The supervisor (launched via `meridian workspace start`) monitors harness CLI events and can detect when a harness compacts/summarizes its conversation. On compaction, the supervisor re-injects skills and pinned context files into the conversation so the agent doesn't lose critical context. This is only possible when meridian owns skill injection — native harness skill loading doesn't give meridian the ability to re-inject after compaction. The two things re-injected on compaction are:
1. Skills — the full skill content
2. Pinned files — context files pinned via `meridian context pin`

```python
# All three adapters:
"agent": FlagStrategy(effect=FlagEffect.DROP)   # meridian decomposes into individual flags
"skills": FlagStrategy(effect=FlagEffect.DROP)  # meridian prompt-injects skill content
```

#### Model — CLI flag (universal)

All three harnesses accept `--model`:
- **Claude**: `--model claude-opus-4-6`
- **Codex**: `--model gpt-5.3-codex`
- **OpenCode**: `--model provider/model` (with prefix stripping via `TRANSFORM` strategy)

Already implemented via `FlagStrategy(effect=FlagEffect.CLI_FLAG, cli_flag="--model")`.

#### Sandbox / Permissions — harness-specific translation

Each harness has a different permission mechanism. Meridian's `PermissionTier` maps to:

| Tier | Claude | Codex | OpenCode |
|------|--------|-------|----------|
| Tier | Claude | Codex (`codex exec`) | OpenCode |
|------|--------|----------------------|----------|
| `read-only` | `--allowedTools Read,Glob,Grep,...` | `-s read-only` | `OPENCODE_PERMISSION` with `{"permissions":{"*":"deny","read":"allow","grep":"allow","glob":"allow","list":"allow"}}` |
| `workspace-write` | `--allowedTools Read,Glob,...,Edit,Write,...` | `-s workspace-write` | `OPENCODE_PERMISSION` with `{"permissions":{"*":"allow"}}` (write tools enabled) |
| `full-access` | `--allowedTools Read,...,Bash,WebFetch,...` | `-s danger-full-access` | `OPENCODE_PERMISSION` with `{"permissions":{"*":"allow"}}` |
| `danger` | `--dangerously-skip-permissions` | `--dangerously-bypass-approvals-and-sandbox` | `OPENCODE_PERMISSION` with danger equivalent (if available) |

**Claude**: Already implemented in `permission_flags_for_harness()` via `--allowedTools`. This replaces what `--agent`'s `permissionMode` and `allowedTools` fields would provide.

**Codex**: Already implemented in `permission_flags_for_harness()` via `-s/--sandbox`. We always use `codex exec` (non-interactive) — sandbox is the sole permission boundary. Other useful flags: `--full-auto` (alias for `-s workspace-write`), `-c key=value` (inline config overrides), `--dangerously-bypass-approvals-and-sandbox`. No `--agent` — codex has no agent concept.

**OpenCode**: Currently returns `[]` (no flags). Use `OPENCODE_PERMISSION` env var (not `OPENCODE_PERMISSION`) — it's purpose-built for permissions and takes precedence over config-level permissions. Accepts JSON with permission keys (`read`, `edit`, `glob`, `grep`, `list`, `bash`, `task`, `skill`, `webfetch`, `websearch`, etc.) mapped to actions (`allow`, `ask`, `deny`). Note: in non-interactive mode (`opencode run`), `ask` auto-rejects, so it effectively equals `deny`. The env var bypasses schema validation, so we must emit well-formed JSON.

#### MCP tool filtering — harness-specific

When agents have `mcp-tools:` in their profile, meridian configures MCP tool filtering per-harness:

| Harness | Mechanism |
|---------|-----------|
| Claude | `--allowedTools "mcp__meridian__run_list,mcp__meridian__run_show,..."` (merged with permission tools) |
| Codex | `enabled_tools` in MCP server config (set during `codex mcp add`) |
| OpenCode | Permission config per-tool in `OPENCODE_PERMISSION` |

See `agent-sandbox-compatibility.md` for MCP server wiring details.

#### Prompt — harness-specific delivery

The composed prompt (with skills baked in) is delivered differently:
- **Claude**: first positional arg to `claude -p <prompt>` (current `PromptMode.FLAG`)
- **Codex**: last positional arg to `codex exec <prompt>` (current `PromptMode.POSITIONAL`)
- **OpenCode**: last positional arg to `opencode run <prompt>` (current `PromptMode.POSITIONAL`)

Already implemented via the `PromptMode` enum in `_strategies.py`.

#### Summary: what each adapter passes to its harness

When `meridian run -a reviewer -s reviewing -p "Review the code"`:

**Claude** receives:
```
claude -p "<composed prompt with reviewing skill + agent body + report instruction + user prompt>"
  --model claude-sonnet-4-6
  --allowedTools "Read,Glob,Grep,Bash(git status),..."
```

**Codex** receives:
```
codex exec
  --model gpt-5.3-codex
  -s read-only
  "<composed prompt with reviewing skill + agent body + report instruction + user prompt>"
```

**OpenCode** receives (with `OPENCODE_PERMISSION` env var set):
```
opencode run
  --model provider/model
  "<composed prompt with reviewing skill + agent body + report instruction + user prompt>"
```

No `--agent` passed to any harness. No `--skills` passed to any harness. Meridian fully owns the agent profile decomposition.

### Precedence chain

For every configurable value:

```
CLI flag > env var > agent profile > config.toml > models.toml > builtin default
```

Existing env vars remain honored:
- `MERIDIAN_REPO_ROOT` — repo root path
- `MERIDIAN_MAX_DEPTH` — max recursion depth
- `MERIDIAN_SUPERVISOR_COMMAND` — supervisor binary override

### What stays internal (not configurable)

- Model-to-harness routing logic (prefix matching in `routing.py`)
- Harness adapter commands and flag construction
- Path conventions (`.meridian/`, `.agents/`)
- Error classification markers (`errors.py`)
- Prompt safety templates (anti-injection, report instructions)
- Permission tier tool allowlists (security — hardcoded per tier)
- Exit code conventions
- SQLite busy timeout

---

## Implementation Slices

### Slice 1: Config loader + `MeridianConfig` dataclass

Create the config loading infrastructure. No CLI commands yet — just the data layer.

**Files to create:**
- `src/meridian/lib/config/settings.py` — `MeridianConfig` frozen dataclass + `load_config(repo_root) -> MeridianConfig` loader

**`MeridianConfig` schema:**
```python
@dataclass(frozen=True, slots=True)
class MeridianConfig:
    max_depth: int = 3
    max_retries: int = 3
    retry_backoff_seconds: float = 0.25
    kill_grace_seconds: float = 2.0
    guardrail_timeout_seconds: float = 30.0
    wait_timeout_seconds: float = 600.0
    default_permission_tier: str = "read-only"
    supervisor_agent: str = "supervisor"
    default_agent: str = "agent"
```

**Loader behavior:**
- If `.meridian/config.toml` missing → return `MeridianConfig()` (all defaults)
- Parse TOML, validate known keys, warn on unknown keys
- Env var overrides applied on top: `MERIDIAN_MAX_DEPTH` overrides `max_depth`, etc.

**Files to modify:**
- None yet — this slice is additive only

**Tests:**
- `tests/test_config_settings.py` — load from fixture TOML, missing file defaults, env var override, unknown key warning

---

### Slice 2: Wire config into consumers (replace hardcoded constants)

Replace module-level constants with `MeridianConfig` dependency injection.

**Files to modify:**
- `src/meridian/lib/ops/run.py` — `DEFAULT_MAX_DEPTH` → `config.max_depth`; poll interval; wait timeout
- `src/meridian/lib/exec/spawn.py` — `DEFAULT_MAX_RETRIES`, `retry_backoff_seconds` → from config
- `src/meridian/lib/exec/timeout.py` — `DEFAULT_KILL_GRACE_SECONDS` → from config
- `src/meridian/lib/safety/guardrails.py` — `timeout_seconds` default → from config
- `src/meridian/lib/safety/permissions.py` — default tier → from config (danger remains opt-in via `--unsafe`)
- `src/meridian/lib/ops/_runtime.py` — load config once, thread through runtime

**Injection approach:**
- `_runtime.py` already builds a `Runtime` object passed to operations
- Add `config: MeridianConfig` field to `Runtime`
- Operations receive config via runtime — no global imports

**Tests:**
- Existing tests continue to pass (config defaults match current hardcoded values)
- New test: custom config overrides propagate to spawn, permissions

---

### Slice 3: Default agent profiles + eliminate base_skills.py

Replace the hardcoded `base_skills.py` with default agent profile resolution.

**Files to modify:**
- `src/meridian/lib/ops/run.py` — when no `--agent` flag is provided, load the default agent profile from config (`defaults.agent`). Fall back gracefully if profile doesn't exist.
- `src/meridian/lib/workspace/launch.py` — load supervisor agent profile from config (`defaults.supervisor_agent`). Use profile's model, skills, sandbox. Fall back to current behavior if profile doesn't exist.
- `src/meridian/lib/prompt/assembly.py` — `resolve_run_defaults()`: remove `mode` parameter. Skills come from the agent profile (which is always resolved by the caller). Remove `BaseSkillMode` concept entirely.
- `src/meridian/lib/config/base_skills.py` — delete this file entirely.

**`mcp_tools` field:**
- `src/meridian/lib/config/agent.py` — add `mcp_tools: tuple[str, ...]` field to `AgentProfile`, parsed from `frontmatter.get("mcp-tools")`. These are bare tool names (e.g., `run_list`), not prefixed. The harness adapter translates them per-harness (Claude: `mcp__meridian__run_list` merged into `--allowedTools`; Codex: `enabled_tools` in MCP server config; OpenCode: per-tool entries in `OPENCODE_PERMISSION`).
- `mcp-tools` stays as a **separate YAML field** from `tools` because: (1) `tools` holds built-in harness tool names (`Read`, `Glob`, `Bash`), (2) MCP tool names are bare and need harness-specific prefixing/translation, (3) the delivery mechanism is fundamentally different per harness.

**Agent profile files to create:**
- `.agents/agents/supervisor.md` — default supervisor profile (skills: run-agent, agent, orchestrate)
- `.agents/agents/agent.md` — default agent profile (skills: run-agent, agent)

**Profile-inferred tier warning:**
- When an agent profile's `sandbox` field infers a tier above `config.default_permission_tier`, log a warning: `"Agent profile '<name>' infers <tier> (config default: <default>). Use --permission to override."` This is informative, not blocking — profiles are repo-controlled and the repo author is responsible.

**Tests:**
- `tests/test_default_agent_profiles.py` — default profile resolution from config, fallback when profile missing, skills loaded from profile not hardcoded
- `mcp_tools` parsed correctly from frontmatter, empty tuple when missing
- Profile-inferred tier warning emitted when tier exceeds config default
- Existing tests pass (default profiles produce same skills as current hardcoded values)

---

### Slice 4a: Drop `--agent` from Claude adapter

Make Claude adapter consistent with codex/opencode: meridian fully decomposes agent profiles into harness primitives.

**Files to modify:**
- `src/meridian/lib/harness/claude.py` — change agent strategy from `CLI_FLAG` to `DROP`:
  ```python
  # Before:
  "agent": FlagStrategy(effect=FlagEffect.CLI_FLAG, cli_flag="--agent"),
  # After:
  "agent": FlagStrategy(effect=FlagEffect.DROP),
  ```
  Claude already receives permissions via `--allowedTools` from `permission_flags_for_harness()`. Model via `--model`. Skills via prompt injection. No reason to also pass `--agent`.

**Tests:**
- Claude adapter no longer passes `--agent` flag
- All existing permission tests continue to pass

---

### Slice 4b: Adapter `env_overrides()` protocol + OpenCode permission injection

Add `env_overrides()` to the `HarnessAdapter` protocol so each adapter can inject harness-specific env vars. This keeps harness-specific logic inside adapters (DIP) — no `if harness_id == "opencode"` in spawn/ops.

**Files to modify:**
- `src/meridian/lib/harness/adapter.py` — add `env_overrides(config: PermissionConfig) -> dict[str, str]` to `HarnessAdapter` protocol. Required method, not optional.
- `src/meridian/lib/harness/claude.py` — implement `env_overrides()` returning `{}`
- `src/meridian/lib/harness/codex.py` — implement `env_overrides()` returning `{}`
- `src/meridian/lib/harness/opencode.py` — implement `env_overrides()` returning `{"OPENCODE_PERMISSION": ...}`
- `src/meridian/lib/exec/spawn.py` — call `adapter.env_overrides()` and merge into child process env. No harness-specific branching in spawn.
- `src/meridian/lib/safety/permissions.py` — add helper `opencode_permission_json(tier: PermissionTier) -> str` used by OpenCode adapter.

**OpenCode permission mapping:**

| Tier | `OPENCODE_PERMISSION` env var |
|------|-------------------------------|
| `read-only` | `{"*":"deny","read":"allow","grep":"allow","glob":"allow","list":"allow"}` |
| `workspace-write` | `{"*":"deny","read":"allow","grep":"allow","glob":"allow","list":"allow","edit":"allow","bash":"deny"}` |
| `full-access` | `{"*":"allow"}` |
| `danger` | `{"*":"allow"}` |

Note: `full-access` and `danger` currently map to the same OpenCode config because `opencode run` (non-interactive) auto-approves everything. This is forward-compatible — when OpenCode adds proper non-interactive permission controls, differentiate the tiers. Emit `logger.warning()` when danger tier is requested for OpenCode to flag the equivalence.

Note: `ask` is avoided since `opencode run` (non-interactive) auto-rejects `ask` actions. Use `deny` for explicit blocking, `allow` for explicit granting.

**Tests:**
- OpenCode adapter injects correct `OPENCODE_PERMISSION` per tier
- Claude/codex adapters return empty env overrides
- Spawn merges env overrides into child process
- All existing permission tests continue to pass

---

### Slice 5: `meridian config` CLI commands

Add the CLI command group for managing config.

**Commands (v1 — minimal):**
- `meridian config init` — scaffold `.meridian/config.toml` with all keys commented out + defaults shown
- `meridian config show` — dump resolved config with source annotations (builtin / file / env var)
- `meridian config set <key> <value>` — set a key in `.meridian/config.toml`
- `meridian config get <key>` — get resolved value for a key
- `meridian config reset <key>` — remove a key from file (reverts to default)

**Files to create:**
- `src/meridian/cli/config_cmd.py` — command implementations
- Register `config_app` in `main.py`

**Files to modify:**
- `src/meridian/cli/main.py` — add `config` command group
- `src/meridian/lib/ops/config.py` — operation specs for config operations (follows existing registry pattern)

**Tests:**
- `tests/test_cli_config.py` — init creates file, set/get roundtrip, reset removes key, show displays sources

---

### Slice 6: Models catalog enhancements

Extend the existing `models.toml` with alias support and role/cost metadata.

No `default = true` flag — the default model comes from the agent profile (`defaults.agent` or `defaults.supervisor_agent` in config.toml). The hardcoded `DEFAULT_MODEL` in `assembly.py` becomes the fallback only when no agent profile is resolved.

**Files to modify:**
- `src/meridian/lib/config/catalog.py` — parse alias mappings, role/cost metadata
- `src/meridian/lib/prompt/assembly.py` — `DEFAULT_MODEL` remains as ultimate fallback (no agent profile, no config)

**`models.toml` example:**
```toml
[models.claude-opus-4-6]
aliases = ["opus", "big"]
role = "Deep reasoning, subtle correctness"
cost_tier = "$$$"

[models.gpt-5.3-codex]
aliases = ["codex", "fast"]
role = "Default implementation"
cost_tier = "$$"
```

**Tests:**
- `tests/test_models_catalog.py` — alias resolution, role/cost metadata parsing, alias collision warning

---

### Slice 7: Configurable search paths for agents and skills

Wire the `[search_paths]` config section into agent/skill discovery. Currently, `_paths.py` returns a single hardcoded canonical directory. This slice adds multi-path scanning with deterministic ordering and collision handling.

**Search path defaults:**

```toml
[search_paths]
# Repo-local paths (relative to repo root)
agents = [".agents/agents", ".claude/agents", ".opencode/agents", ".cursor/agents"]
skills = [".agents/skills", ".claude/skills", ".opencode/skills", ".cursor/skills"]

# User-global paths (absolute, expanded from ~)
global_agents = ["~/.claude/agents", "~/.opencode/agents"]
global_skills = ["~/.claude/skills", "~/.opencode/skills"]
```

**Resolution order:** Repo-local paths are scanned first, then global paths. Within each list, order is as written. First match wins on name collision — a repo-local `.agents/agents/reviewer.md` shadows a global `~/.claude/agents/reviewer.md`.

**Files to modify:**
- `src/meridian/lib/config/settings.py` — add `SearchPathConfig` to `MeridianConfig`:
  ```python
  @dataclass(frozen=True, slots=True)
  class SearchPathConfig:
      agents: tuple[str, ...] = (".agents/agents", ".claude/agents", ".opencode/agents", ".cursor/agents")
      skills: tuple[str, ...] = (".agents/skills", ".claude/skills", ".opencode/skills", ".cursor/skills")
      global_agents: tuple[str, ...] = ("~/.claude/agents", "~/.opencode/agents")
      global_skills: tuple[str, ...] = ("~/.claude/skills", "~/.opencode/skills")
  ```
- `src/meridian/lib/config/_paths.py` — replace `canonical_agents_dir()` / `canonical_skills_dir()` with `resolve_search_paths(config: SearchPathConfig, repo_root: Path) -> list[Path]` that expands `~`, resolves relative paths against repo root, and filters to existing directories.
- `src/meridian/lib/config/agent.py` — `scan_agent_profiles()` accepts a list of directories, scans all, applies first-match-wins on name collision, logs warning on collision.
- `src/meridian/lib/config/skill_registry.py` — same multi-path scanning for skills.

**Collision handling:**
- First match wins (by search path order).
- Log `logger.warning("Agent profile '<name>' found in multiple paths: <path1>, <path2>. Using <path1>.")` on collision.
- No crash — the first-match-wins rule is deterministic and predictable.

**Tests:**
- `tests/test_search_paths.py` — multi-path scanning, first-match-wins, collision warning, `~` expansion, missing directories skipped, global paths after repo-local

---

## Verification

Each slice:
1. All existing tests pass (no behavior change for default config)
2. `uv run ruff check src/ tests/`
3. `uv run pyright src/`
4. New tests for the slice

## Risks

- **Danger tier safety**: Config must NEVER allow setting `default_permission_tier = "danger"`. Validate on load.
- **Missing default profiles**: If `.agents/agents/supervisor.md` or `agent.md` doesn't exist, must fall back gracefully to current hardcoded behavior. Profiles are not required — they enhance the defaults.
- **Profile vs config precedence**: When both a default profile and CLI flags are provided, CLI flags win. Profile provides defaults, not overrides.
- **Profile-inferred tier escalation**: A default agent profile with `sandbox: unrestricted` silently gives every `meridian run` `full-access` tier (up from the `read-only` default). Mitigated by warning log (see Slice 3), but repo owners should be aware.
- **OpenCode permission mapping**: `opencode run` currently auto-approves all actions in non-interactive mode. The `OPENCODE_PERMISSION` injection may not have effect until OpenCode respects per-tool permissions in non-interactive mode. This is forward-compatible — we set the config now, it takes effect when OpenCode supports it. `full-access` and `danger` tiers are currently identical for OpenCode; emit a warning when danger is requested.
- **Double injection guard**: After dropping `--agent` from Claude, verify no other code path re-introduces it. The `FlagStrategy` system is the single point of control.
- **Model alias collisions**: If two models in `models.toml` claim the same alias (e.g., both claim `"fast"`), warn on load and use the first match. Don't crash — the catalog should be usable even with minor config mistakes.
- **TOML type validation**: Validate types on load, not just unknown keys. `max_depth = "three"` must fail with a clear error message pointing to the offending key and expected type.
- **Atomic config writes**: `meridian config set` and `meridian config reset` must use write-to-temp-file + atomic rename to prevent corruption from concurrent writes or interrupted operations.
- **Search path collision**: When the same agent/skill name exists in multiple search paths, first-match-wins is deterministic but may surprise users. Warn on collision (see Slice 7).
