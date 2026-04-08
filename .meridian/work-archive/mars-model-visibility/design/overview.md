# Model Visibility Filtering — Design Overview

## Problem

`mars models list` shows every alias in the merged set (builtins + deps + consumer). As catalogs grow, the output becomes noisy. Users need display-level filtering without affecting model resolution.

## Scope

- **Display filter only** — affects `mars models list` output (table and JSON modes)
- **Does NOT affect `mars models resolve`** — hidden aliases still resolve normally
- **Does NOT interact with dep-level `FilterConfig`** — different concern, different pipeline stage
- Glob matching against alias names in the final merged set

## Components

Three changes, each detailed in [visibility-filtering.md](visibility-filtering.md):

1. **Config schema** — new `ModelVisibility` struct on `Settings`, parsed from `[settings.model_visibility]` in mars.toml
2. **Filtering function** — `filter_by_visibility()` in `src/models/mod.rs`, reusing existing `glob_match()`
3. **CLI integration** — `--include` / `--exclude` flags on `mars models list`, overriding config when present

## Key Design Decisions

- Reuse existing `glob_match()` — no new dependencies (see decisions.md §D1)
- Separate `ModelVisibility` struct, not reuse of `FilterConfig` — different concern (see §D2)
- **`[settings.model_visibility]` not `[models.visibility]`** — visibility is a consumer preference, not package metadata. `[models]` flows through deps; `[settings]` is consumer-only. This follows the universal pattern: Cargo (`[patch]`/`[profile]` are workspace-only), Go (`replace`/`exclude` are main-module-only), Python (`[tool.*]` is consumer config). No custom deserializer needed, no reserved alias name collision. (see §D3)
- CLI flags override config entirely, not merge (see §D4)
- Filtering logic in models module, not CLI layer (see §D5)
- Mutual exclusivity validated at config load time (see §D6)

## Files Modified

| File | Change |
|---|---|
| `src/config/mod.rs` | Add `ModelVisibility` struct to `Settings`; add validation |
| `src/models/mod.rs` | Add `filter_by_visibility()` function |
| `src/cli/models.rs` | Add `--include`/`--exclude` to `ListArgs` with `conflicts_with`; load visibility from settings; apply filter in `run_list()` |
