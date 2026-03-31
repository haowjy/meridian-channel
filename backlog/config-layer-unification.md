# Config Layer Unification

## Problem

Meridian has five configuration layers that have diverged: CLI flags, ENV vars, agent YAML profiles, project config TOML, and user config TOML. Fields are added to one layer but not others, naming is inconsistent (`autocompact_pct` vs `autocompact`), and the precedence chain isn't enforced through shared infrastructure. Adding a new field requires touching 5+ files independently.

## Precedence

```
CLI > ENV > YAML profile > Project Config > User Config > harness default
```

- **CLI** — you explicitly typed it, highest intent
- **ENV** — `MERIDIAN_*` vars, personal/CI override without editing files
- **YAML profile** — this agent's baked-in defaults
- **Project Config** — this repo's team settings (`.meridian/config.toml`)
- **User Config** — global personal preferences (`~/.meridian/config.toml`)
- **Harness default** — what the harness does on its own

Key change from current state: ENV is currently baked into config via pydantic-settings (`builtin < project TOML < user TOML < env`). This refactor separates ENV into its own layer between CLI and profile. Config loading becomes purely TOML-based. Project TOML wins over User TOML (currently inverted).

## Architecture: RuntimeOverrides

### Core idea

Define universal "tuning knob" fields ONCE in a shared Pydantic model. Every layer uses this same model. Adding a field = add it to `RuntimeOverrides`, done. No drift possible.

```python
class RuntimeOverrides(BaseModel):
    """Fields that can be set at any config layer."""
    model: str | None = None
    harness: str | None = None
    effort: str | None = None
    sandbox: str | None = None
    approval: str | None = None
    autocompact: int | None = None
    timeout: float | None = None
```

### Resolution

One function, five layers, explicit precedence:

```python
def resolve(
    cli: RuntimeOverrides,       # from --flags
    env: RuntimeOverrides,       # from MERIDIAN_* vars (read separately, not via pydantic-settings)
    profile: RuntimeOverrides,   # from agent YAML frontmatter
    project: RuntimeOverrides,   # from project TOML
    user: RuntimeOverrides,      # from user TOML
) -> RuntimeOverrides:
    resolved = {}
    for field in RuntimeOverrides.model_fields:
        resolved[field] = first_non_none(
            getattr(cli, field),
            getattr(env, field),
            getattr(profile, field),
            getattr(project, field),
            getattr(user, field),
        )
    return RuntimeOverrides(**resolved)
```

### Layer composition

Each existing model composes `RuntimeOverrides`:
- `PrimaryConfig` embeds or inherits RuntimeOverrides fields (TOML source)
- `AgentProfile` has RuntimeOverrides fields (YAML source, parsed from frontmatter)
- `SpawnCreateInput` / `LaunchRequest` has RuntimeOverrides fields (CLI source)
- ENV is read into a RuntimeOverrides instance directly from `MERIDIAN_*` vars

Layer-specific fields stay on their own models:
- `AgentProfile`: name, description, skills, tools, mcp_tools, body, path
- `SpawnCreateInput`: prompt, files, context_from, desc, work, background, etc.
- Config: max_depth, max_retries, retry_backoff, kill_grace, primary_agent, default_agent, per-harness model defaults

### Harness mapping

Harness-specific flag translation (approval → `--dangerously-skip-permissions`, effort → `--effort`, etc.) stays adapter-owned. `RuntimeOverrides` carries abstract values; adapters translate. This is not the registry's job.

### What this replaces

- Scattered precedence logic in `prepare.py`, `plan.py`, `resolve.py` → one `resolve()` function
- Independent field definitions in 5 models → one `RuntimeOverrides` model
- Hand-maintained consistency tests → structural impossibility of drift
- pydantic-settings ENV loading → explicit ENV parsing into RuntimeOverrides

## Current State Matrix

| Field | ENV | CLI (spawn) | CLI (primary) | YAML | Project Config | User Config |
|-------|-----|-------------|---------------|------|---------------|-------------|
| model | `MERIDIAN_MODEL` | `--model` | `--model` | ✅ | `primary.model` | `primary.model` |
| harness | `MERIDIAN_HARNESS` | `--harness` | `--harness` | ✅ | `primary.harness` | `primary.harness` |
| effort | ❌ | `--effort` | ❌ | ✅ | ❌ | ❌ |
| sandbox | ❌ | `--sandbox` | ❌ | ✅ | ❌ | ❌ |
| approval | ❌ | `--approval` | `--yolo` only | ✅ | ❌ | ❌ |
| autocompact | ❌ | `--autocompact` | `--autocompact` | ✅ | `autocompact_pct` ⚠️ | `autocompact_pct` ⚠️ |
| timeout | ❌ | `--timeout` | ❌ | ❌ | ❌ | ❌ |

### Target state (after refactor)

Every RuntimeOverrides field present in ALL applicable layers:

| Field | ENV | CLI (spawn) | CLI (primary) | YAML | Project Config | User Config |
|-------|-----|-------------|---------------|------|---------------|-------------|
| model | `MERIDIAN_MODEL` | `--model` | `--model` | ✅ | ✅ | ✅ |
| harness | `MERIDIAN_HARNESS` | `--harness` | `--harness` | ✅ | ✅ | ✅ |
| effort | `MERIDIAN_EFFORT` | `--effort` | `--effort` | ✅ | ✅ | ✅ |
| sandbox | `MERIDIAN_SANDBOX` | `--sandbox` | `--sandbox` | ✅ | ✅ | ✅ |
| approval | `MERIDIAN_APPROVAL` | `--approval` | `--approval` | ✅ | ✅ | ✅ |
| autocompact | `MERIDIAN_AUTOCOMPACT` | `--autocompact` | `--autocompact` | ✅ | ✅ | ✅ |
| timeout | `MERIDIAN_TIMEOUT` | `--timeout` | `--timeout` | ✅ | ✅ | ✅ |

### Fields that stay layer-specific

| Field | Layers | Reason |
|-------|--------|--------|
| tools, mcp-tools | YAML only | Complex structured data |
| skills | YAML + CLI | Per-agent/invocation, not a global default |
| max_depth, max_retries, kill_grace | Config + ENV only | Global safety limits |
| primary_agent, default_agent | Config + ENV only | Role-based defaults (orchestrator vs subagent) |
| work, desc, background, continue, fork | CLI only | Runtime context |
| per-harness model defaults | Config + ENV only | Harness routing |

## Refactor Plan

### Phase 1: Create RuntimeOverrides model
- Define `RuntimeOverrides` in a new shared module (e.g., `lib/core/overrides.py`)
- Include all 9 universal fields with validation
- Add `from_env()` classmethod that reads `MERIDIAN_*` vars into an instance
- Add `from_agent_profile()` that extracts overrides from an AgentProfile
- Add `from_config()` that extracts from PrimaryConfig
- Write the `resolve()` function

### Phase 2: Rip ENV out of pydantic-settings config loading
- Stop pydantic-settings from reading `MERIDIAN_*` for RuntimeOverrides fields
- Config loading becomes purely TOML: `builtin defaults < User TOML < Project TOML`
- Fix precedence: project wins over user (currently inverted)
- ENV is read separately via `RuntimeOverrides.from_env()`

### Phase 3: Wire resolution through spawn + primary paths
- Replace scattered precedence logic in `prepare.py`, `plan.py`, `resolve.py` with calls to `resolve()`
- Both spawn and primary launch use the same resolution function
- Single source of truth for precedence

### Phase 4: Close remaining gaps
- Add missing fields to each layer per the target state matrix
- Rename `autocompact_pct` → `autocompact` (deprecated alias)
- Add `--approval`, `--effort`, `--sandbox`, `--timeout`, `--budget`, `--max-turns` to primary CLI
- Add missing ENV vars

### Phase 5: Naming convention enforcement
- Validate at test time: every RuntimeOverrides field has a matching ENV var (`MERIDIAN_` + UPPER_SNAKE), config key (`primary.<field>`), and CLI flag (`--<field>`)
- This test is structural — it introspects RuntimeOverrides.model_fields, not a hand-maintained list

## Reviewer feedback incorporated

- **No single god-registry** (p419) — RuntimeOverrides is just a Pydantic model, not a metadata table with callbacks. Harness mapping stays adapter-owned.
- **Introspect, don't hand-maintain** (p421, p423) — Phase 5 test introspects RuntimeOverrides.model_fields, not a static list. No KNOWN_GAPS to game.
- **Don't bless dead fields** (p423) — only add CLI flags for fields that have real consumers in the launch/spawn pipeline. budget and max_turns were removed entirely as dead fields with no pipeline consumers.
- **Resolve in one place** (p423) — `resolve()` replaces duplicated precedence logic in prepare.py and plan.py.
- **Phase 3.3 was too big** (p421, p422) — split into Phase 2 (config loading) and Phase 3 (resolution wiring) as separate steps.
- **Config precedence was inverted** (p422) — project TOML now wins over user TOML.
