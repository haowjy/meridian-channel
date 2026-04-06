# Visibility Filtering — Detailed Design

## 1. Config Schema

### mars.toml surface

```toml
[models.visibility]
include = ["opus*", "sonnet*", "gpt-*"]
# OR
exclude = ["test-*", "deprecated-*"]
```

Only one of `include` or `exclude` may be set. Both set → validation error at config load time.

### Rust types

```rust
// src/config/mod.rs

/// Display visibility filter for `mars models list`.
/// Consumer-only — deps cannot set this.
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
pub struct VisibilityConfig {
    /// Show only aliases matching these glob patterns.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub include: Option<Vec<String>>,
    /// Hide aliases matching these glob patterns.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub exclude: Option<Vec<String>>,
}
```

### Config struct change

The current `Config` has:
```rust
pub struct Config {
    pub models: IndexMap<String, ModelAlias>,
    // ...
}
```

This needs to accommodate both alias definitions (`[models.opus]`) and the visibility sub-table (`[models.visibility]`). Two approaches:

**Chosen: Custom deserialization.** Implement a custom deserializer for the models field that:
1. Deserializes the TOML table
2. Extracts the `visibility` key into `VisibilityConfig` if present
3. Deserializes remaining keys as `ModelAlias` entries

This keeps the `Config` struct clean:
```rust
pub struct Config {
    pub package: Option<PackageInfo>,
    pub dependencies: IndexMap<SourceName, Dependency>,
    pub settings: Settings,
    pub models: IndexMap<String, ModelAlias>,
    #[serde(default)]
    pub models_visibility: Option<VisibilityConfig>,
}
```

**Alternative considered:** A wrapper `ModelsSection` struct with `#[serde(flatten)]`. This is cleaner conceptually but `#[serde(flatten)]` with mixed typed/untyped keys in TOML has edge cases. The custom deserializer is more explicit and avoids serde flatten pitfalls.

**Simplest alternative (recommended):** Since `visibility` is not a valid model alias name (it would conflict), we can use a simpler approach — deserialize as `IndexMap<String, toml::Value>`, pop the `visibility` key, deserialize the rest as aliases. This avoids a full custom Deserialize impl while staying straightforward:

```rust
// In Config, change models to a raw intermediate during deser:
fn deserialize_models_section(table: &toml::Value) -> (IndexMap<String, ModelAlias>, Option<VisibilityConfig>) {
    let map = table.as_table().unwrap_or(/* empty */);
    let visibility = map.get("visibility")
        .and_then(|v| VisibilityConfig::deserialize(v).ok());
    let aliases = map.iter()
        .filter(|(k, _)| *k != "visibility")
        .map(|(k, v)| (k.clone(), ModelAlias::deserialize(v)))
        // collect, handle errors
        ;
    (aliases, visibility)
}
```

### Validation

```rust
impl VisibilityConfig {
    pub fn validate(&self) -> Result<(), MarsError> {
        if self.include.is_some() && self.exclude.is_some() {
            return Err(MarsError::Config(
                "[models.visibility] cannot have both 'include' and 'exclude'".into()
            ));
        }
        Ok(())
    }

    pub fn is_empty(&self) -> bool {
        self.include.is_none() && self.exclude.is_none()
    }
}
```

Call `visibility.validate()` in the config loading path, alongside existing `validate_filter()` calls.

## 2. Filtering Function

Located in `src/models/mod.rs`, reusing existing `glob_match()`:

```rust
/// Filter resolved aliases by visibility config.
/// - `include` patterns: keep only aliases where at least one pattern matches
/// - `exclude` patterns: remove aliases where any pattern matches
/// - No config (both None): return all aliases unchanged
pub fn filter_by_visibility(
    aliases: IndexMap<String, ResolvedAlias>,
    visibility: &VisibilityConfig,
) -> IndexMap<String, ResolvedAlias> {
    if let Some(includes) = &visibility.include {
        aliases.into_iter()
            .filter(|(name, _)| includes.iter().any(|p| glob_match(p, name)))
            .collect()
    } else if let Some(excludes) = &visibility.exclude {
        aliases.into_iter()
            .filter(|(name, _)| !excludes.iter().any(|p| glob_match(p, name)))
            .collect()
    } else {
        aliases // no filtering
    }
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
    #[arg(long, value_delimiter = ',')]
    include: Option<Vec<String>>,
    /// Hide aliases matching these patterns (overrides config).
    #[arg(long, value_delimiter = ',')]
    exclude: Option<Vec<String>>,
}
```

CLI validation: error if both `--include` and `--exclude` are passed.

### run_list() changes

```rust
fn run_list(args: &ListArgs, ctx: &MarsContext, json: bool) -> Result<i32, MarsError> {
    // ... existing load + merge + resolve ...

    // Build effective visibility: CLI overrides config entirely
    let visibility = if args.include.is_some() || args.exclude.is_some() {
        // CLI provided — validate mutual exclusivity
        if args.include.is_some() && args.exclude.is_some() {
            return Err(MarsError::Config(
                "cannot use both --include and --exclude".into()
            ));
        }
        VisibilityConfig {
            include: args.include.clone(),
            exclude: args.exclude.clone(),
        }
    } else {
        // Fall back to config
        load_visibility_config(ctx)
    };

    // Apply visibility filter
    let filtered = models::filter_by_visibility(resolved, &visibility);

    // ... existing table/json output using `filtered` instead of `resolved` ...
}
```

### load_visibility_config helper

```rust
fn load_visibility_config(ctx: &MarsContext) -> VisibilityConfig {
    crate::config::load(&ctx.project_root)
        .ok()
        .and_then(|c| c.models_visibility)
        .unwrap_or_default()
}
```

## 4. What Does NOT Change

- `run_resolve()` — no visibility filtering, hidden aliases still resolve
- `run_alias()` — adding an alias is unaffected by visibility
- `run_refresh()` — cache fetching is unaffected
- `FilterConfig` — dep-level filtering is a separate concern
- `Manifest` struct — lock file doesn't store visibility
- `builtin_aliases()` — builtins are filtered at display time, not at definition time

## 5. Example mars.toml

```toml
[models.visibility]
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
