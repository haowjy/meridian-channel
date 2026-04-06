# Configuration

## `mars.toml` Schema Addition

Add one field to `[settings]` in `src/config/mod.rs::Settings`:

```rust
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
pub struct Settings {
    // ...existing fields...

    /// How long the models cache is considered fresh, in hours.
    /// `0` means always refresh on read. Default: 24.
    #[serde(default = "default_models_cache_ttl_hours")]
    pub models_cache_ttl_hours: u32,
}

fn default_models_cache_ttl_hours() -> u32 {
    24
}
```

A custom serde default (rather than `Default::default() = 0`) is
important: `Default` for `u32` is `0`, and `0` has a special meaning
("always refresh"), so we must not let the field default to `0` when the
user simply omitted it from `mars.toml`.

## User-facing TOML

```toml
[settings]
models_cache_ttl_hours = 24    # default; can omit entirely
# models_cache_ttl_hours = 0   # always refresh (useful for CI)
# models_cache_ttl_hours = 168 # one week, for long-lived dev envs
```

## Validation

No validation beyond serde type parsing. `u32` range is sufficient; any
value (including 0 and `u32::MAX`) is legal. `u32::MAX * 3600` overflows
`u64::MAX / 3600` only at absurd values; compute the threshold as
`(now_secs - fetched_secs) < (ttl_hours as u64) * 3600` and accept that
`ttl=u32::MAX` effectively means "never stale", which is a reasonable
outcome for users who want to opt out of automatic refresh without
dealing with `MARS_OFFLINE`.

## Config Precedence Fit

Mars's existing config layering (`mars.toml` → `mars.local.toml`) applies
as-is — the new field is a plain `Settings` member. No special precedence
rules.

Meridian's config layering (see `CLAUDE.md` → "Config Precedence") is
unaffected because meridian never reads `models_cache_ttl_hours`; it's a
mars-side setting consumed entirely inside `ensure_fresh`.

## Defaults Reasoning

24 hours balances:

- **User irritation** from refresh chatter on every `mars models list`.
- **Catalog drift**: new Claude/GPT releases land roughly weekly; a
  24-hour TTL means a user sees new models within a day of a release
  without ever running `mars models refresh` manually.
- **CI behavior**: CI jobs typically start with a cold `.mars/`, so the
  first `sync` or `models list` pays the fetch cost once. Subsequent
  invocations within the same run inherit the fresh cache.

If the default proves wrong in practice, it's a one-line change — no
schema migration.

## Documentation Changes

- Add the field to the `settings` section of mars-agents's README /
  `mars.toml` reference.
- Add a short note in meridian-channel's CLAUDE.md under "Dev Workflow":
  if you're doing offline development, set `MARS_OFFLINE=1` or bump
  `models_cache_ttl_hours` high in `mars.toml`.

Documentation is a separate phase at the end of the plan, after the
implementation has converged.
