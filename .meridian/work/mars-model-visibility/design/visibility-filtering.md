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

This needs to accommodate both alias definitions (`[models.opus]`) and the visibility sub-table (`[models.visibility]`). 

**Chosen approach:** Custom `#[serde(deserialize_with)]` on a models field that splits `visibility` from alias entries. This follows the same pattern as the existing `RawModelAlias` intermediate deserialization in `src/models/mod.rs`.

The `Config` struct becomes:
```rust
pub struct Config {
    pub package: Option<PackageInfo>,
    pub dependencies: IndexMap<SourceName, Dependency>,
    pub settings: Settings,
    #[serde(default, deserialize_with = "deserialize_models_section")]
    pub models: IndexMap<String, ModelAlias>,
    #[serde(skip)]
    pub models_visibility: Option<VisibilityConfig>,
}
```

The custom deserializer:
```rust
/// Deserialize [models] table, extracting the `visibility` sub-key separately.
/// All other keys are deserialized as ModelAlias entries.
fn deserialize_models_section<'de, D>(
    deserializer: D,
) -> Result<IndexMap<String, ModelAlias>, D::Error>
where
    D: serde::Deserializer<'de>,
{
    let mut table: IndexMap<String, toml::Value> = IndexMap::deserialize(deserializer)?;
    // Remove visibility — it's handled separately in a post-deser pass
    table.remove("visibility");
    let mut aliases = IndexMap::new();
    for (key, value) in table {
        let alias: ModelAlias = ModelAlias::deserialize(value).map_err(serde::de::Error::custom)?;
        aliases.insert(key, alias);
    }
    Ok(aliases)
}
```

The `visibility` field is populated in a post-deserialization pass within `config::load()`:
```rust
pub fn load(root: &Path) -> Result<Config, MarsError> {
    let content = std::fs::read_to_string(root.join("mars.toml"))?;
    let mut config: Config = toml::from_str(&content)?;
    
    // Extract visibility from raw TOML (skipped by serde)
    let raw: toml::Value = toml::from_str(&content)?;
    if let Some(models_table) = raw.get("models") {
        if let Some(vis_value) = models_table.get("visibility") {
            let vis: VisibilityConfig = vis_value.clone().try_into()
                .map_err(|e| MarsError::Config(format!("invalid [models.visibility]: {e}")))?;
            vis.validate()?;
            config.models_visibility = Some(vis);
        }
    }
    
    // ... existing migration, validation ...
    Ok(config)
}
```

**Why not `#[serde(flatten)]`:** Mixed typed and untyped keys under flatten with the `toml` crate has known edge cases — tagged enum variants can fail to deserialize when flattened alongside a catch-all map. The explicit extract-then-parse approach is more reliable.

**Reserved name:** `run_alias()` must reject "visibility" as an alias name since it would collide with the config sub-table.

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

**Critical: config errors must propagate.** The existing code swallows config load errors via `.ok()` and `if let Ok(...)`. For visibility validation to surface errors (e.g., both include and exclude set), `run_list()` must propagate config load results. Refactor `load_merged_aliases` to return visibility alongside aliases:

```rust
struct MergedModels {
    aliases: IndexMap<String, ModelAlias>,
    visibility: Option<VisibilityConfig>,
}

fn load_merged_aliases(ctx: &MarsContext) -> Result<MergedModels, MarsError> {
    let mut merged = models::builtin_aliases();
    
    // Layer dep aliases (existing logic)
    // ...
    
    // Layer consumer config — propagate errors, don't swallow
    let visibility = if let Ok(config) = crate::config::load(&ctx.project_root) {
        for (name, alias) in &config.models {
            merged.insert(name.clone(), alias.clone());
        }
        config.models_visibility
    } else {
        None
    };
    
    Ok(MergedModels { aliases: merged, visibility })
}
```

Then in `run_list()`:

```rust
fn run_list(args: &ListArgs, ctx: &MarsContext, json: bool) -> Result<i32, MarsError> {
    let mars = mars_dir(ctx);
    let cache = models::read_cache(&mars)?;
    let merged_models = load_merged_aliases(ctx)?;
    let resolved = models::resolve_all(&merged_models.aliases, &cache);

    // Build effective visibility: CLI overrides config entirely
    let visibility = if args.include.is_some() || args.exclude.is_some() {
        VisibilityConfig {
            include: args.include.clone(),
            exclude: args.exclude.clone(),
        }
    } else {
        merged_models.visibility.unwrap_or_default()
    };

    // Apply visibility filter (mutates in place via retain)
    let filtered = models::filter_by_visibility(resolved, &visibility);

    // ... existing table/json output using `filtered` instead of `resolved` ...
}
```

Note: CLI mutual exclusivity is enforced by clap's `conflicts_with` (see ListArgs above), so no runtime check needed in `run_list()`.

## 4. What Does NOT Change

- `run_resolve()` — no visibility filtering, hidden aliases still resolve
- `run_alias()` — adding an alias is unaffected by visibility, but must reject "visibility" as an alias name
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
