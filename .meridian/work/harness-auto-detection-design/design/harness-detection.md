# Harness Detection

## Installed Harness Detection

Mars detects which harness CLIs are available by checking for binaries on `$PATH`.

```rust
// src/models/harness.rs (new file)

/// Known harness binaries and the binary name to check.
const HARNESS_BINARIES: &[(&str, &str)] = &[
    ("claude", "claude"),
    ("codex", "codex"),
    ("opencode", "opencode"),
    ("gemini", "gemini"),
];

/// Check which harness CLIs are installed.
/// Returns the set of harness names whose binaries are found on $PATH.
pub fn detect_installed_harnesses() -> HashSet<String> {
    HARNESS_BINARIES.iter()
        .filter(|(_, binary)| which::which(binary).is_ok())
        .map(|(name, _)| name.to_string())
        .collect()
}
```

**No caching.** Detection runs on every `resolve` call. `which` checks are ~2ms total for 4 binaries — negligible compared to the subprocess overhead of spawning an agent. Caching would introduce staleness bugs (user installs a new harness mid-session) for no measurable performance gain.

**Dependency:** Add the [`which`](https://crates.io/crates/which) crate to mars-agents. It's a small, well-maintained crate that handles cross-platform binary lookup (Windows `where`, Unix `which`).

## Provider-to-Harness Preference Table

Each provider has an ordered preference list of harnesses. Mars tries them in order and picks the first one that's installed.

```rust
/// Default provider → harness preference order.
/// First installed harness wins.
const PROVIDER_HARNESS_PREFERENCES: &[(&str, &[&str])] = &[
    ("anthropic", &["claude", "opencode", "gemini"]),
    ("openai",    &["codex", "opencode"]),
    ("google",    &["gemini", "opencode"]),
    ("meta",      &["opencode"]),
    ("mistral",   &["opencode"]),
    ("deepseek",  &["opencode"]),
    ("cohere",    &["opencode"]),
];
```

**Resolution algorithm:**

```
fn resolve_harness_for_provider(provider: &str, installed: &HashSet<String>) -> Option<String> {
    // 1. Look up preference list for this provider (case-insensitive)
    // 2. Return first harness in the list that's in `installed`
    // 3. If none installed, return None (alias is unavailable)
}
```

## mars.toml Override

Users can override the default preference table in mars.toml:

```toml
[harness]
# Override which binary maps to which harness name
# (for when someone has a non-standard binary name)
# NOT for changing preference order — that's the provider table above.

[harness.preferences]
# Override the preference order for a provider
anthropic = ["opencode", "claude"]  # prefer opencode over claude
openai = ["opencode"]               # never use codex
```

This is stored in a new `HarnessConfig` struct:

```rust
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
pub struct HarnessConfig {
    #[serde(default, skip_serializing_if = "IndexMap::is_empty")]
    pub preferences: IndexMap<String, Vec<String>>,
}
```

The merge: mars.toml preferences override the hardcoded defaults per-provider. Providers not mentioned in mars.toml use the defaults.

## When No Harness is Available

If a model alias can't resolve to any installed harness:
- `mars models list` **omits** it (user can't run it anyway)
- `mars models resolve <alias>` returns an error with a message like: `"No installed harness supports provider 'Anthropic'. Install one of: claude, opencode, gemini"`
- The JSON output includes `"harness": null` with an `"error"` field

This lets meridian distinguish "alias resolved but no harness" from "unknown alias" and give appropriate user-facing messages.
