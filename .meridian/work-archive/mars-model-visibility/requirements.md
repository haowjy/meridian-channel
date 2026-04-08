# Model Visibility Filtering

## Problem
`mars models list` dumps every alias in the merged set (builtins + deps + consumer). As the catalog grows, the list gets noisy. Users need to filter what they see.

## Requirements

### Config-based filtering
- New `[models.visibility]` section in consumer `mars.toml`
- `include` — list of glob patterns; only show matching alias names
- `exclude` — list of glob patterns; hide matching alias names
- Mutually exclusive (pick one, error if both set)
- Consumer-only — deps cannot set visibility for the consumer
- Filters apply to the final merged alias set (builtins + deps + consumer)

### CLI ad-hoc filtering
- `mars models list --include "gpt-*"`
- `mars models list --exclude "test-*"`
- CLI flags **override** config entirely (not additive) — consistent with existing config precedence (CLI > config)

### Scope boundaries
- Display filter only — affects `mars models list` output
- Does NOT affect `mars models resolve` — hidden aliases still resolve
- Does NOT interact with dep-level FilterConfig (agents/skills/exclude) — different concern, different stage
- Glob matching against alias names in the merged set

## Success criteria
- Config include/exclude works with glob patterns
- CLI flags override config when present
- `mars models resolve hidden-alias` still works on excluded aliases
- Validation error if both include and exclude are set in config
- JSON output mode respects the same filters
