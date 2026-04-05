# Resolve API

## New: ResolvedAlias Type

```rust
/// Fully resolved model alias — everything a consumer needs to launch.
#[derive(Debug, Clone, Serialize)]
pub struct ResolvedAlias {
    pub name: String,
    pub model_id: String,
    pub provider: String,
    pub harness: Option<String>,     // None = no installed harness available
    pub harness_source: String,      // "explicit", "auto-detected", "unavailable"
    pub description: Option<String>,
}
```

## resolve_all Changes

The current `resolve_all` returns `IndexMap<String, String>` (alias → model_id). Replace with:

```rust
pub fn resolve_all(
    aliases: &IndexMap<String, ModelAlias>,
    cache: &ModelsCache,
    installed_harnesses: &HashSet<String>,
    harness_preferences: &IndexMap<String, Vec<String>>,  // from config
) -> Vec<ResolvedAlias> {
    aliases.iter().filter_map(|(name, alias)| {
        // 1. Resolve model ID (pinned or auto-resolve)
        let (model_id, provider) = match &alias.spec {
            ModelSpec::Pinned { model } => {
                let provider = infer_provider_from_model_id(model)
                    .unwrap_or("unknown").to_string();
                (model.clone(), provider)
            }
            ModelSpec::AutoResolve { provider, match_patterns, exclude_patterns } => {
                let id = auto_resolve(provider, match_patterns, exclude_patterns, cache)?;
                (id, provider.clone())
            }
        };

        // 2. Resolve harness
        let (harness, harness_source) = if let Some(h) = &alias.harness {
            // Explicit harness — use it regardless of installation
            (Some(h.clone()), "explicit".to_string())
        } else {
            // Auto-detect from provider
            match resolve_harness_for_provider(&provider, installed_harnesses, harness_preferences) {
                Some(h) => (Some(h), "auto-detected".to_string()),
                None => (None, "unavailable".to_string()),
            }
        };

        Some(ResolvedAlias {
            name: name.clone(),
            model_id,
            provider,
            harness,
            harness_source,
            description: alias.description.clone(),
        })
    }).collect()
}
```

## `mars models list` Changes

The list command gains awareness of harness availability:

- **Default (no flags):** Only show aliases that resolved to a model ID AND have an available harness.
- **`--all`:** Show all aliases including those with no available harness (marked with `—` in harness column).
- **JSON output:** Always includes all aliases with `harness: null` for unavailable ones.

```
$ mars models list
ALIAS        HARNESS    MODE           RESOLVED                       DESCRIPTION
opus         claude     auto-resolve   claude-opus-4-6                Best reasoning
sonnet       claude     auto-resolve   claude-sonnet-4-5              Fast + capable
gpt          codex      auto-resolve   gpt-5.3-codex                 OpenAI flagship

$ mars models list --all
ALIAS        HARNESS    MODE           RESOLVED                       DESCRIPTION
opus         claude     auto-resolve   claude-opus-4-6                Best reasoning
sonnet       claude     auto-resolve   claude-sonnet-4-5              Fast + capable
haiku        claude     auto-resolve   claude-haiku-4-5               Fast and cheap
codex        —          auto-resolve   codex-mini-latest              (no harness: install codex)
gpt          codex      auto-resolve   gpt-5.3-codex                 OpenAI flagship
gemini       —          auto-resolve   gemini-2.5-pro                 (no harness: install opencode)
```

## `mars models resolve <alias>` Changes

### Text Output

```
$ mars models resolve opus
Alias:    opus
Source:   builtin
Provider: Anthropic
Harness:  claude (auto-detected)
Mode:     auto-resolve
Match:    *opus*
Resolved: claude-opus-4-6
```

### JSON Output

```json
{
  "name": "opus",
  "source": "builtin",
  "provider": "Anthropic",
  "harness": "claude",
  "harness_source": "auto-detected",
  "model_id": "claude-opus-4-6",
  "spec": {
    "mode": "auto-resolve",
    "provider": "Anthropic",
    "match": ["*opus*"],
    "exclude": []
  },
  "description": null
}
```

When no harness is available:

```json
{
  "name": "gemini",
  "source": "builtin",
  "provider": "Google",
  "harness": null,
  "harness_source": "unavailable",
  "harness_candidates": ["gemini", "opencode"],
  "model_id": "gemini-2.5-pro",
  "error": "No installed harness for provider 'Google'. Install one of: gemini, opencode"
}
```

## New: `mars harness list`

Simple command showing detected harnesses:

```
$ mars harness list
HARNESS    BINARY    STATUS
claude     claude    installed
codex      codex     installed
opencode   opencode  not found
gemini     gemini    not found
```

JSON:
```json
{
  "harnesses": [
    {"name": "claude", "binary": "claude", "installed": true},
    {"name": "codex", "binary": "codex", "installed": true},
    {"name": "opencode", "binary": "opencode", "installed": false},
    {"name": "gemini", "binary": "gemini", "installed": false}
  ]
}
```

This is a diagnostic tool — useful for debugging "why doesn't my alias work?" problems.

## Performance

The resolve API adds harness detection (~8ms for 4 `which` checks) to every `mars models resolve` call. Since meridian already pays ~50-100ms subprocess overhead to call mars, this is negligible.

For `mars models list`, harness detection runs once per invocation (not per alias).
