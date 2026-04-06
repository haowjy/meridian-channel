# Decision Log — Model Visibility Filtering

## D1: Reuse existing `glob_match` instead of adding a crate dependency

**Decision:** Use the existing `models::glob_match()` function for alias name matching in visibility filters.

**Reasoning:** `glob_match` already exists in `src/models/mod.rs`, is tested, handles `*` wildcards, and is `pub`. The visibility feature matches alias names (short strings like "opus", "gpt-*"), which is the same complexity level as the model ID matching `glob_match` already handles. No need for `globset`/`glob` crates — the existing function does exactly what we need.

**Rejected:** Adding `glob` or `globset` crate. These support `?`, `[a-z]`, `**` and other features unnecessary for alias name matching. Adding a dependency for features we don't need violates simplicity.

## D2: New `VisibilityConfig` struct, not reuse `FilterConfig`

**Decision:** Create a new `VisibilityConfig` struct with `include: Option<Vec<String>>` and `exclude: Option<Vec<String>>` fields, rather than reusing `FilterConfig`.

**Reasoning:** `FilterConfig` handles dep-level agent/skill filtering with `only_agents`, `only_skills`, `agents`, `skills`, `exclude`, and `rename` fields — a fundamentally different concern (what to materialize from a dependency). Visibility filtering is a display concern (what to show in `mars models list`). Reusing `FilterConfig` would:
- Confuse two unrelated filtering stages
- Force visibility to carry irrelevant fields (`only_agents`, `rename`, etc.)
- Create coupling between dependency resolution and display formatting

**Rejected:** Reuse `FilterConfig` — wrong abstraction level, different concern entirely.

## D3: Place `visibility` inside existing `[models]` table, not as a top-level section

**Decision:** Use `[models.visibility]` in mars.toml. Parse via custom `deserialize_with` on the models field that strips the `visibility` key before deserializing remaining keys as `ModelAlias` entries. Populate `Config.models_visibility` in a post-deserialization pass within `config::load()`.

**Reasoning:** Visibility filtering is scoped to models — it makes semantic sense as a sub-table of `[models]`. TOML parsing creates a tension: `[models]` currently deserializes as `IndexMap<String, ModelAlias>`, and adding a `visibility` key would collide. The custom deserializer approach is explicit and avoids serde flatten edge cases with mixed typed/untyped keys. The name "visibility" is reserved and cannot be used as an alias name.

**Rejected:**
- Top-level `[visibility]` — unclear what it filters without the `models.` prefix.
- `#[serde(flatten)]` wrapper struct — known edge cases with TOML crate when mixing typed fields and catch-all maps.
- Full custom `Deserialize` impl on `Config` — overkill; `deserialize_with` on the single field is sufficient.

## D4: CLI flags override config entirely, not merge

**Decision:** When `--include` or `--exclude` CLI flags are present on `mars models list`, they completely replace any `[models.visibility]` config. No merging.

**Reasoning:** Consistent with the project's config precedence principle (CLI > config). Merging creates confusing interactions — "I passed `--include gpt-*` but some GPT models are hidden because config has `exclude = ["gpt-4"]`" is a bad UX. Override-not-merge is how every other CLI flag works in this project.

## D5: Filtering function lives in `models/mod.rs`, not in CLI layer

**Decision:** Create a `filter_by_visibility(aliases: &IndexMap<String, ResolvedAlias>, visibility: &VisibilityConfig) -> IndexMap<String, ResolvedAlias>` function in the models module.

**Reasoning:** The filtering logic is model-domain logic (glob matching against alias names), not CLI formatting logic. Placing it in `models/mod.rs` makes it testable without CLI scaffolding and reusable if other commands need the same filter (e.g., a future `models export`).

## D6: Return visibility from load_merged_aliases to avoid double config parse

**Decision:** Refactor `load_merged_aliases()` in `src/cli/models.rs` to return a `MergedModels` struct containing both the alias map and the visibility config, instead of parsing config separately for visibility.

**Reasoning:** The existing `load_merged_aliases()` already calls `config::load()`. Adding a separate `load_visibility_config()` helper would parse the config file a second time. Returning both from the same load is simpler and ensures config validation errors (including visibility validation) propagate through the same path.

**Constraint discovered:** The existing code swallows `config::load()` errors via `.ok()` and `if let Ok(...)`. For visibility validation to surface errors (e.g., both include and exclude set), the config load result must propagate. This is a pre-existing design gap that visibility filtering exposes — config errors should not be silently dropped.

## D7: Validate include/exclude mutual exclusivity at config load time

**Decision:** Validate that `include` and `exclude` are mutually exclusive in `VisibilityConfig::validate()`, called during config loading — not deferred to command execution.

**Reasoning:** Fail-fast. A user with both set in their config file should see the error on any `mars models list` invocation, not silently have one win. This matches how `validate_filter` works for `FilterConfig` — validation at load time, not use time.
