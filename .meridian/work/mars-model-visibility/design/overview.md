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

1. **Config schema** — new `VisibilityConfig` struct, parsed from `[models.visibility]` in mars.toml
2. **Filtering function** — `filter_by_visibility()` in `src/models/mod.rs`, reusing existing `glob_match()`
3. **CLI integration** — `--include` / `--exclude` flags on `mars models list`, overriding config when present

## Key Design Decisions

- Reuse existing `glob_match()` — no new dependencies (see decisions.md §D1)
- Separate `VisibilityConfig` struct, not reuse of `FilterConfig` — different concern (see §D2)
- `[models.visibility]` nested under models table, not top-level (see §D3)
- CLI flags override config entirely, not merge (see §D4)
- Filtering logic in models module, not CLI layer (see §D5)
- Mutual exclusivity validated at config load time (see §D6)

## Files Modified

| File | Change |
|---|---|
| `src/config/mod.rs` | Add `VisibilityConfig` struct; add custom deserializer for `[models]` table to extract `visibility` key; add validation; populate `Config.models_visibility` in `load()` |
| `src/models/mod.rs` | Add `filter_by_visibility()` function |
| `src/cli/models.rs` | Add `--include`/`--exclude` to `ListArgs` with `conflicts_with`; refactor `load_merged_aliases` to return visibility; apply filter in `run_list()`; reject "visibility" as alias name in `run_alias()` |
