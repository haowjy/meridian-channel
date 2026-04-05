# Model Alias Schema Changes

## ModelAlias Type

`harness` becomes `Option<String>`:

```rust
pub struct ModelAlias {
    pub harness: Option<String>,       // was: String
    pub description: Option<String>,
    pub spec: ModelSpec,
}
```

## RawModelAlias Deserialization

```rust
struct RawModelAlias {
    harness: Option<String>,           // was: String (required)
    description: Option<String>,
    model: Option<String>,
    provider: Option<String>,
    match_patterns: Option<Vec<String>>,
    exclude: Option<Vec<String>>,
}
```

No validation change needed — `harness` was already parsed from TOML which treats missing keys as `None` for `Option` types. The custom `Deserialize` impl just passes it through.

## mars.toml Backwards Compatibility

Existing configs with explicit harness still work unchanged:

```toml
# Still works — harness is forced to claude
[models.opus]
harness = "claude"
provider = "Anthropic"
match = ["*opus*"]

# New style — harness auto-detected from provider
[models.opus]
provider = "Anthropic"
match = ["*opus*"]

# Pinned with explicit harness — still works
[models.fast]
harness = "claude"
model = "claude-haiku-4-5"

# Pinned without harness — auto-detected from model ID patterns
[models.fast]
model = "claude-haiku-4-5"
```

## Builtin Aliases

All builtin aliases drop the harness field:

```rust
pub fn builtin_aliases() -> IndexMap<String, ModelAlias> {
    let mut m = IndexMap::new();
    let add = |m: &mut IndexMap<String, ModelAlias>,
               name: &str,
               provider: &str,
               match_patterns: &[&str],
               exclude: &[&str]| {
        m.insert(
            name.to_string(),
            ModelAlias {
                harness: None,  // auto-detected at resolution time
                description: None,
                spec: ModelSpec::AutoResolve {
                    provider: provider.to_string(),
                    match_patterns: match_patterns.iter().map(|s| s.to_string()).collect(),
                    exclude_patterns: exclude.iter().map(|s| s.to_string()).collect(),
                },
            },
        );
    };
    add(&mut m, "opus", "anthropic", &["*opus*"], &[]);
    add(&mut m, "sonnet", "anthropic", &["*sonnet*"], &[]);
    add(&mut m, "haiku", "anthropic", &["*haiku*"], &[]);
    add(&mut m, "codex", "openai", &["*codex*"], &["*-mini", "*-spark", "*-max"]);
    add(&mut m, "gpt", "openai", &["gpt-5*"], &["*codex*", "*-mini", "*-nano", "*-chat", "*-turbo"]);
    add(&mut m, "gemini", "google", &["gemini*", "*pro*"], &["*-customtools"]);
    m
}
```

## Pinned Aliases Without Provider

When a pinned alias has no `harness` and no `provider`, mars needs to infer the provider from the model ID to route to a harness. This uses simple prefix matching:

```rust
fn infer_provider_from_model_id(model_id: &str) -> Option<&'static str> {
    if model_id.starts_with("claude-") { return Some("anthropic"); }
    if model_id.starts_with("gpt-") || model_id.starts_with("o1") 
       || model_id.starts_with("o3") || model_id.starts_with("o4")
       || model_id.starts_with("codex-") { return Some("openai"); }
    if model_id.starts_with("gemini") { return Some("google"); }
    if model_id.starts_with("llama") { return Some("meta"); }
    if model_id.starts_with("mistral") || model_id.starts_with("codestral") { return Some("mistral"); }
    if model_id.starts_with("deepseek") { return Some("deepseek"); }
    if model_id.starts_with("command") { return Some("cohere"); }
    None
}
```

If inference fails, the alias is treated as having no harness (meridian's own routing in `model_policy.py` handles it as a fallback).

## Serialization

When serializing `ModelAlias` to JSON (for `models-merged.json`, `resolve --json`), `harness` is included only when explicitly set:

```rust
// In Serialize impl:
if let Some(h) = &self.harness {
    map.serialize_entry("harness", h)?;
}
```

## Impact on merge_model_config

No change to merge logic. The merge algorithm compares by alias name, not by harness. When two aliases have the same name, the higher-precedence one wins entirely (including its harness value, whether Some or None).

## Impact on resolve_all

`resolve_all` currently returns `IndexMap<String, String>` (alias → model_id). It needs to be extended to also return the resolved harness. See [resolve-api.md](resolve-api.md) for the new return type.
