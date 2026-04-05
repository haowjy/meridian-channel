# Decision Log

## D1: Provider→harness preference table hardcoded in mars

**Decision:** The provider-to-harness preference table is hardcoded as a Rust constant in mars, with an optional mars.toml `[harness.preferences]` override.

**Alternatives rejected:**
- **Fully configurable (mars.toml only):** Would require every project to configure the table, or mars to ship a default config file. The table changes rarely (new harnesses appear maybe yearly), and hardcoding keeps it inspectable with no config files.
- **Live in meridian instead of mars:** Would make `mars models list` unable to show harness info standalone. Mars needs to resolve harnesses independently since it's the single source of truth for model aliases.

**Constraints:** Mars must work standalone (without meridian) for the `mars models list` and `mars models resolve` commands to be useful diagnostics tools.

## D2: No caching for harness detection

**Decision:** `which` binary checks run on every `resolve` / `list` invocation with no caching.

**Alternatives rejected:**
- **Cache on first call, invalidate on session boundary:** Adds complexity (where to store? how to invalidate?) for ~8ms savings. The subprocess overhead of calling mars is already 50-100ms.
- **Cache in `.mars/harness-cache.json`:** Creates staleness bugs — user installs a new harness and mars doesn't see it until cache expires.

**Constraints:** Detection must be fast enough for per-spawn use. 4 `which` checks at ~2ms each = ~8ms total, well within budget.

## D3: Pinned aliases without provider use model ID inference

**Decision:** When a pinned alias has `model = "claude-opus-4-6"` but no `harness` and no `provider`, mars infers the provider from model ID prefixes (`claude-` → anthropic, `gpt-` → openai, etc.).

**Alternatives rejected:**
- **Require provider for all aliases without harness:** Would break existing pinned aliases in mars.toml that only specify `model`. Users shouldn't need to add `provider` when the model ID makes it obvious.
- **Fall through to meridian's routing:** Would mean `mars models list` can't show harness info for these aliases, making the standalone mars experience worse.

**Constraint:** The inference is best-effort. Unknown model ID prefixes get `harness: null`, and meridian's routing handles them.

## D4: `mars models list` hides unavailable aliases by default

**Decision:** The default `mars models list` only shows aliases where both model resolution AND harness detection succeeded. `--all` shows everything.

**Alternatives rejected:**
- **Always show all aliases:** Confusing — users see aliases they can't use with no explanation. The `--all` flag exists for debugging.
- **Show unavailable aliases with a warning suffix:** Clutters the default output. The table format already shows harness, so `—` in the harness column (with `--all`) is sufficient.

## D5: `harness_source` field in resolve output

**Decision:** The resolve JSON includes `harness_source: "explicit" | "auto-detected" | "unavailable"` so consumers can distinguish how the harness was chosen.

**Rationale:** Debugging harness routing is hard without knowing whether the harness came from the alias config or auto-detection. This field costs nothing to include and makes `mars models resolve` a complete diagnostic tool.

## D6: Add `which` crate dependency

**Decision:** Use the `which` crate for cross-platform binary detection instead of raw `std::process::Command::new("which")`.

**Rationale:** `which` handles Windows (`where`), PATH parsing, and edge cases (symlinks, permissions). Rolling our own is more code for worse correctness.

## D7: No changes to meridian's model_policy.py

**Decision:** Meridian's existing harness routing (`DEFAULT_HARNESS_PATTERNS`, `route_model_with_patterns`) is unchanged.

**Rationale:** Meridian already handles the case where mars doesn't provide a harness — the `AliasEntry.harness` property falls back to pattern-based routing. Mars adding auto-detection improves the mars-side experience but doesn't change meridian's resolution path. Keeping meridian's routing as a fallback also means meridian still works if mars is unavailable or returns partial data.

## D8: New `mars harness list` command

**Decision:** Add a simple diagnostic command showing detected harnesses and their installation status.

**Alternatives rejected:**
- **Only expose through `mars models list --verbose`:** Users debugging "why doesn't my alias work?" shouldn't need to parse model list output to find harness info.
- **Skip it — let users run `which` themselves:** Users shouldn't need to know the binary names for each harness.

**Constraint:** Must be simple — just a list of harness names, binary names, and installed/not-found status.
