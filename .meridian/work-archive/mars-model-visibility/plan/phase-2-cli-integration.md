# Phase 2: CLI Integration

## Scope

Wire `ModelVisibility` and `filter_by_visibility()` into the `mars models list` command. Add `--include`/`--exclude` CLI flags that override config. This completes the feature.

## Files to Modify

### `src/cli/models.rs`

1. **Add `--include` and `--exclude` flags to `ListArgs`** (currently at line 31-35, only has `all: bool`):

```rust
#[derive(Debug, Parser)]
pub struct ListArgs {
    /// Show all aliases including those without an available harness.
    #[arg(long)]
    all: bool,
    /// Only show aliases matching these patterns (overrides config).
    #[arg(long, value_delimiter = ',', conflicts_with = "exclude")]
    include: Option<Vec<String>>,
    /// Hide aliases matching these patterns (overrides config).
    #[arg(long, value_delimiter = ',', conflicts_with = "include")]
    exclude: Option<Vec<String>>,
}
```

Clap's `conflicts_with` enforces mutual exclusivity at the CLI level — no runtime check needed.

2. **Update `run_list()`** (starts at line 97) to load visibility and apply filter:

After `resolve_all()` (line 103) and before the output loop, add:

```rust
// Build effective visibility: CLI overrides config entirely
let config_visibility = crate::config::load(&ctx.project_root)
    .map(|c| c.settings.model_visibility)
    .unwrap_or_default();

let visibility = if args.include.is_some() || args.exclude.is_some() {
    crate::config::ModelVisibility {
        include: args.include.clone(),
        exclude: args.exclude.clone(),
    }
} else {
    config_visibility
};

let resolved = models::filter_by_visibility(resolved, &visibility);
```

**Important:** Check how config is currently loaded in `run_list()`. It may already call `config::load()` or access settings through a different path. If config is already available, reuse it instead of loading again. The key behavior: CLI flags override config entirely (not merge).

**Note on variable shadowing:** The existing code uses `resolved` as the variable name from `resolve_all()`. Either shadow it with `let resolved = models::filter_by_visibility(resolved, &visibility);` or use a new name like `filtered` — whichever matches the existing code style. If using a new name, update all downstream references in both the JSON output path (lines 105-134) and the table output path (lines 136-162).

3. **Verify both output paths use the filtered result:**
   - JSON mode (lines 105-134): iterates over resolved aliases
   - Table mode (lines 136-162): iterates over resolved aliases
   - Both must use the post-filter result

## Dependencies

- **Requires:** Phase 1 — `ModelVisibility` type and `filter_by_visibility()` function
- **Independent of:** No other pending work

## Interface Contract

From Phase 1:
- `crate::config::ModelVisibility` — struct with `include: Option<Vec<String>>`, `exclude: Option<Vec<String>>`, derives `Default`
- `models::filter_by_visibility(IndexMap<String, ResolvedAlias>, &ModelVisibility) -> IndexMap<String, ResolvedAlias>`

## Patterns to Follow

- Existing `ListArgs` struct (line 31) — same derive macros, `#[arg(long)]` style
- Existing `run_list()` flow (line 97) — load → resolve → filter → display
- Config loading pattern in other commands — check `run_resolve()` or `run_alias()` for how they access config

## Verification Criteria

- [ ] `cargo build` succeeds
- [ ] `cargo test` passes
- [ ] `mars models list --include "opus*"` shows only opus-matching aliases
- [ ] `mars models list --exclude "test-*"` hides test-prefixed aliases
- [ ] `mars models list --include "x" --exclude "y"` produces a clap error (mutual exclusivity)
- [ ] With `[settings.model_visibility]` in mars.toml, `mars models list` respects the config
- [ ] CLI flags override config: config has `include = ["opus*"]`, `--exclude "gpt-*"` replaces it entirely
- [ ] `mars models resolve <hidden-alias>` still works (resolve is unaffected)
- [ ] `cargo clippy` passes
