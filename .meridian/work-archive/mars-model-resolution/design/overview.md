# Design: Mars as Single Authority for Model→Harness Resolution

## Problem

Meridian maintains its own model→harness routing in `src/meridian/lib/catalog/model_policy.py` via glob-based `harness_patterns` (`claude-*` → claude, `gpt-*` → codex, etc.) and a user-configurable `[harness_patterns]` section in `.meridian/models.toml`. Mars now has equivalent functionality — provider→harness preference tables, installed CLI detection, and harness auto-detection — built into its alias resolution. The two systems are redundant, can disagree, and both need maintenance when new models or harnesses are added.

When a user runs `meridian spawn -m opus`, the resolution currently:
1. Checks mars aliases → finds `opus` → resolves to `claude-opus-4-6`
2. Then falls back to meridian's `route_model()` with harness_patterns to determine the harness
3. The harness embedded in the mars alias is ignored or overridden by meridian's pattern matching

This creates meridian issue #5: the alias resolves correctly but meridian's pattern matching may fail or disagree with mars's harness determination.

## Goal

Make mars the single authority for "given this model identifier, what harness runs it?" Meridian keeps ownership of:
- **Precedence**: CLI > env > profile > config layer merging
- **Spawn orchestration**: building commands, managing processes
- **Compatibility validation**: checking that the resolved harness is registered and supports primary launch
- **Final model string resolution**: harness-specific config defaults

Mars owns:
- **Alias resolution**: short name → concrete model ID
- **Harness determination**: model ID → harness (via explicit alias field, provider inference, or installed CLI detection)

## Design Summary

See [resolution-flow.md](resolution-flow.md) for the new resolution algorithm.
See [removal-map.md](removal-map.md) for what gets removed from meridian.
See [mars-api.md](mars-api.md) for the mars interface contract.

## Key Decisions

1. **CLI integration, not Python import** — meridian calls `mars models resolve <name> --json` (new command) rather than importing mars as a Python library. Mars is a Rust binary; no Python bindings exist. The existing `mars models list --json` pattern already works well.

2. **Harness patterns stay as fallback** — when mars is unavailable or the model isn't in any alias, meridian's `DEFAULT_HARNESS_PATTERNS` remain as a hardcoded last resort. This prevents breakage when mars isn't installed. But `.meridian/models.toml [harness_patterns]` user config is removed — users configure model→harness in `mars.toml` instead.

3. **AliasEntry.harness becomes authoritative** — today `_resolve_alias_harness()` backfills the harness by calling `route_model()`. After this change, the harness comes from mars's resolution (the `harness` field in mars's JSON output) and is trusted directly.

4. **`models.toml` scope shrinks** — the `[harness_patterns]` section is removed. `[model_visibility]` stays (it's a meridian-only display concern). The file may eventually be removed entirely but that's out of scope.
