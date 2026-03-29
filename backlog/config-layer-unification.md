# Config Layer Unification

## Problem

Meridian has four configuration layers that have diverged: ENV vars, config TOML, agent YAML profiles, and CLI flags. Fields are added to one layer but not others, naming is inconsistent (`autocompact_pct` vs `autocompact`), and the precedence chain isn't enforced through shared infrastructure.

## Current State

### Full matrix (as of March 2026)

| Field | ENV var | Config TOML | YAML Profile | Spawn CLI | Primary CLI |
|-------|---------|-------------|-------------|-----------|-------------|
| model | `MERIDIAN_MODEL` | `primary.model` + `default_model` | `model` | `--model` | `--model` |
| harness | `MERIDIAN_HARNESS` | `primary.harness` + `default_harness` | `harness` | ❌ (p418) | `--harness` |
| skills | ❌ | ❌ | `skills` | `--skills` | ❌ |
| tools | ❌ | ❌ | `tools` | ❌ | ❌ |
| mcp_tools | ❌ | ❌ | `mcp_tools` | ❌ | ❌ |
| sandbox | ❌ | ❌ | `sandbox` | ❌ (p418) | ❌ |
| thinking | ❌ | ❌ | `thinking` | ❌ (p418) | ❌ |
| approval | ❌ | ❌ | `approval` | `--yolo` only | `--yolo` only |
| autocompact | ❌ | `primary.autocompact_pct` ⚠️ | `autocompact` | ❌ (p418) | `--autocompact` |
| timeout | ❌ | ❌ | ❌ | `--timeout` | ❌ |
| budget | `MERIDIAN_BUDGET` | `primary.budget` | ❌ | ❌ | ❌ |
| max_turns | `MERIDIAN_MAX_TURNS` | `primary.max_turns` | ❌ | ❌ | ❌ |
| max_input_tokens | `MERIDIAN_MAX_INPUT_TOKENS` | `primary.max_input_tokens` | ❌ | ❌ | ❌ |
| max_output_tokens | `MERIDIAN_MAX_OUTPUT_TOKENS` | `primary.max_output_tokens` | ❌ | ❌ | ❌ |
| max_depth | `MERIDIAN_MAX_DEPTH` | `max_depth` | ❌ | ❌ | ❌ |
| max_retries | `MERIDIAN_MAX_RETRIES` | `max_retries` | ❌ | ❌ | ❌ |
| agent | `MERIDIAN_AGENT` | `primary.agent` + `primary_agent` + `default_agent` | — (is the profile) | `--agent` | `--agent` |
| work | ❌ | ❌ | ❌ | `--work` | `--work` |

### Naming inconsistencies
- Config: `autocompact_pct` vs YAML/CLI: `autocompact`
- Config: `primary_agent` vs `default_agent` vs `primary.agent` (three fields for agent defaults)
- ENV: `MERIDIAN_DEFAULT_HARNESS` vs `MERIDIAN_HARNESS` (which one wins?)

## Design: Unified Field Registry

### Principle

Define each field ONCE in a registry. The registry entry specifies:
- **name**: canonical field name (used in YAML and CLI)
- **type**: int, str, float, bool
- **valid_values**: optional set of allowed values (e.g., `{default, confirm, auto, yolo}`)
- **range**: optional min/max for numeric fields
- **layers**: which layers this field appears in (`{env, config, yaml, cli_spawn, cli_primary}`)
- **env_var**: `MERIDIAN_*` name (derived from name if not specified)
- **config_path**: TOML path (e.g., `primary.autocompact`)
- **harness_mapping**: per-harness flag translation (for fields that map to harness CLI flags)

From this single definition, generate:
- AgentProfile field + parser
- SpawnCreateInput / LaunchRequest field
- Config key spec + template
- ENV var spec
- CLI flag (via cyclopts Parameter)
- Validation logic

### Which fields go where

**Universal fields** (all layers): model, harness, thinking, sandbox, approval, autocompact, timeout, budget, max_turns

**YAML + CLI only** (per-agent/invocation, not global defaults): skills, tools, mcp_tools

**Config + ENV only** (global operational tuning): max_depth, max_retries, retry_backoff_seconds, kill_grace_minutes

**CLI only** (runtime, not defaults): work, desc, dry_run, verbose, quiet, background, continue, fork

### Precedence

```
CLI flag > YAML profile > Config TOML > ENV var > harness default
```

Each layer overrides the one below. `None`/unset means "fall through to next layer."

### Naming convention

- Field name is the same everywhere: `autocompact` (not `autocompact_pct` in config)
- ENV var is `MERIDIAN_` + UPPER_SNAKE: `MERIDIAN_AUTOCOMPACT`
- Config TOML path: `primary.autocompact` or top-level for globals
- CLI flag: `--autocompact`
- YAML key: `autocompact`

## Refactor Plan

### Phase 1: Rename for consistency (non-breaking)
- Config: rename `autocompact_pct` → `autocompact` (keep old name as deprecated alias)
- Config: consolidate `primary_agent`/`default_agent`/`primary.agent` — clarify which does what

### Phase 2: Field registry
- Create a `FieldSpec` model that defines one field across all layers
- Create the registry as a tuple of FieldSpec entries
- Generate AgentProfile fields, SpawnCreateInput fields, config key specs, and ENV var specs from it
- Validate at import time that all layers are in sync

### Phase 3: Close gaps
- Add missing fields to each layer per the matrix above
- Add missing ENV vars (MERIDIAN_APPROVAL, MERIDIAN_THINKING, MERIDIAN_SANDBOX, etc.)
- Ensure primary CLI and spawn CLI have matching flags for universal fields

### Phase 4: Harness mapping unification
- Centralize the field → harness flag translation (currently scattered across permissions.py, harness adapters, and SpawnParams strategies)
- Each FieldSpec optionally carries a harness_mapping that translates the abstract value to per-harness CLI flags

## Risk

The field registry is a significant abstraction. If it's too magical (code generation, metaclasses), it becomes harder to understand than the duplication it replaces. Keep it simple: a data table that's validated at import time, not a code generator. The actual CLI/YAML/config code can still be explicit — the registry just ensures they stay in sync.
