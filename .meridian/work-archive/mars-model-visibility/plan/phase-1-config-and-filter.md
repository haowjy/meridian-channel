# Phase 1: Config Schema + Filtering Function

## Scope

Add the `ModelVisibility` type to config and the `filter_by_visibility()` function to the models module. This phase produces the types and logic that Phase 2 consumes — no CLI changes yet.

## Files to Modify

### `src/config/mod.rs`

1. **Add `ModelVisibility` struct** (near `FilterConfig`, around line 71):

```rust
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

2. **Add `validate()` and `is_empty()` methods** on `ModelVisibility`:

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

3. **Add `model_visibility` field to `Settings`** (currently has `managed_root` and `targets`):

```rust
pub struct Settings {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub managed_root: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub targets: Option<Vec<String>>,
    #[serde(default, skip_serializing_if = "ModelVisibility::is_empty")]
    pub model_visibility: ModelVisibility,
}
```

4. **Call `model_visibility.validate()`** in the config loading/validation path. Look for where `validate_filter()` is called (around line 332 in `merge_with_root()`) and add validation for the consumer config's settings. The validation should run during config loading — fail-fast on invalid config.

**Note on `MarsError::Config` variant:** Check the actual error type. The design says `MarsError::Config(...)` but the codebase may use `ConfigError` or a different variant. Match the existing pattern — look at how `validate_filter()` returns errors.

### `src/models/mod.rs`

1. **Add `filter_by_visibility()` function** (after `resolve_all()`, around line 606):

```rust
/// Filter resolved aliases by visibility config.
/// - `include` patterns: keep only aliases where at least one pattern matches
/// - `exclude` patterns: remove aliases where any pattern matches
/// - No config (both None): return all aliases unchanged
pub fn filter_by_visibility(
    mut aliases: IndexMap<String, ResolvedAlias>,
    visibility: &crate::config::ModelVisibility,
) -> IndexMap<String, ResolvedAlias> {
    if let Some(includes) = &visibility.include {
        aliases.retain(|name, _| includes.iter().any(|p| glob_match(p, name)));
    } else if let Some(excludes) = &visibility.exclude {
        aliases.retain(|name, _| !excludes.iter().any(|p| glob_match(p, name)));
    }
    aliases
}
```

This reuses the existing `glob_match()` function at line 401.

## Dependencies

- **Requires:** Nothing — this is the foundation phase.
- **Produces:** `ModelVisibility` type and `filter_by_visibility()` function, consumed by Phase 2.

## Patterns to Follow

- `FilterConfig` struct (line 71-84 in config/mod.rs) — same derive macros, serde attributes, validation pattern.
- `validate_filter()` (line 394-430 in config/mod.rs) — same error handling style for mutual exclusivity.
- `glob_match()` usage in `auto_resolve()` (line 378-382 in models/mod.rs) — same matching semantics.

## Verification Criteria

- [ ] `cargo build` succeeds
- [ ] `cargo test` passes — add unit tests for:
  - `ModelVisibility::validate()` — both set returns error, one set or neither passes
  - `ModelVisibility::is_empty()` — both None returns true, either set returns false
  - `filter_by_visibility()` — include mode keeps matches only, exclude mode removes matches, empty config returns all unchanged
- [ ] A `mars.toml` with `[settings.model_visibility]` having both `include` and `exclude` produces a validation error
- [ ] A `mars.toml` with only `include` or only `exclude` under `[settings.model_visibility]` parses successfully
- [ ] `cargo clippy` passes
