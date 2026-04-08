# Visibility Filtering — Detailed Design

## 1. Config Schema

### mars.toml surface

```toml
[settings.model_visibility]
include = ["opus*", "sonnet*", "gpt-*"]
# OR
exclude = ["test-*", "deprecated-*"]
```

Only one of `include` or `exclude` may be set. Both set → validation error at config load time.

Lives under `[settings]` because visibility is a consumer preference — it should never flow through the dependency graph. `[models]` aliases flow through deps; `[settings]` is consumer-only. This follows the universal pattern across package managers (see decisions.md §D3).

### Rust types

```rust
// src/config/mod.rs

/// Display visibility filter for `mars models list`.
/// Consumer-only — lives under [settings], not [models].
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
pub struct ModelVisibility {
    /// Show only aliases matching these glob patterns.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub include: Option<Vec<String>>,
    /// Hide aliases matching these glob patterns.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub exclude: Option<Vec<String>>,
}
```

### Settings struct change

The existing `Settings` struct gains one field:

```rust
pub struct Settings {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub managed_root: Option<String>,
    #[serde(default, skip_serializing_if = "ModelVisibility::is_empty")]
    pub model_visibility: ModelVisibility,
}
```

No changes to `Config` struct, no custom deserializers, no reserved alias names. Serde handles `[settings.model_visibility]` natively as a nested table on `Settings`.

### Validation

```rust
impl ModelVisibility {
    pub fn validate(&self) -> Result<(), MarsError> {
        if self.include.is_some() && self.exclude.is_some() {
            return Err(MarsError::Config(
                "[settings.model_visibility] cannot have both 'include' and 'exclude'".into()
            ));
        }
        Ok(())
    }

    pub fn is_empty(&self) -> bool {
        self.include.is_none() && self.exclude.is_none()
    }
}
```

Call `model_visibility.validate()` in the config loading path, alongside existing `validate_filter()` calls.

## 2. Filtering Function

Located in `src/models/mod.rs`, reusing existing `glob_match()`:

```rust
/// Filter resolved aliases by visibility config.
/// - `include` patterns: keep only aliases where at least one pattern matches
/// - `exclude` patterns: remove aliases where any pattern matches
/// - No config (both None): return all aliases unchanged
pub fn filter_by_visibility(
    mut aliases: IndexMap<String, ResolvedAlias>,
    visibility: &VisibilityConfig,
) -> IndexMap<String, ResolvedAlias> {
    if let Some(includes) = &visibility.include {
        aliases.retain(|name, _| includes.iter().any(|p| glob_match(p, name)));
    } else if let Some(excludes) = &visibility.exclude {
        aliases.retain(|name, _| !excludes.iter().any(|p| glob_match(p, name)));
    }
    aliases
}
```

Semantics:
- **Include mode:** alias is visible if **any** include pattern matches (OR)
- **Exclude mode:** alias is hidden if **any** exclude pattern matches (OR)
- Matching uses `glob_match()` — `*` matches any character sequence, everything else is literal, case-sensitive

## 3. CLI Integration

### ListArgs changes

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

Mutual exclusivity is enforced by clap's `conflicts_with` — clap emits the error before `run_list()` is called.

### run_list() changes

Load visibility from settings, let CLI override:

```rust
fn run_list(args: &ListArgs, ctx: &MarsContext, json: bool) -> Result<i32, MarsError> {
    let mars = mars_dir(ctx);
    let cache = models::read_cache(&mars)?;
    let merged = load_merged_aliases(ctx)?;
    let resolved = models::resolve_all(&merged, &cache);

    // Build effective visibility: CLI overrides config entirely
    let config_visibility = crate::config::load(&ctx.project_root)
        .map(|c| c.settings.model_visibility)
        .unwrap_or_default();

    let visibility = if args.include.is_some() || args.exclude.is_some() {
        ModelVisibility {
            include: args.include.clone(),
            exclude: args.exclude.clone(),
        }
    } else {
        config_visibility
    };

    // Apply visibility filter
    let filtered = models::filter_by_visibility(resolved, &visibility);

    // ... existing table/json output using `filtered` instead of `resolved` ...
}
```

Note: CLI mutual exclusivity is enforced by clap's `conflicts_with` (see ListArgs above), so no runtime check needed in `run_list()`. The existing `load_merged_aliases` function is unchanged — visibility comes from settings, not the alias merge pipeline.

## 4. What Does NOT Change

- `run_resolve()` — no visibility filtering, hidden aliases still resolve
- `run_alias()` — adding an alias is unaffected by visibility
- `run_refresh()` — cache fetching is unaffected
- `FilterConfig` — dep-level filtering is a separate concern
- `Manifest` struct — lock file doesn't store visibility
- `builtin_aliases()` — builtins are filtered at display time, not at definition time

## 5. Example mars.toml

```toml
[settings.model_visibility]
include = ["opus*", "sonnet*", "gpt-*"]

[models.opus]
provider = "Anthropic"
match = ["opus"]

[models.custom-test]
model = "test-model-123"
harness = "claude"
```

With this config, `mars models list` shows only aliases matching `opus*`, `sonnet*`, or `gpt-*`. The `custom-test` alias would be hidden from the list but `mars models resolve custom-test` still works.

`mars models list --exclude "test-*"` overrides the config include list entirely, showing everything except test-prefixed aliases.
