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

## D3: Place visibility under `[settings]`, not `[models]`

**Decision:** Use `[settings.model_visibility]` in mars.toml. Add `ModelVisibility` as a field on the existing `Settings` struct.

**Reasoning:** Visibility is a consumer preference — it should never flow through the dependency graph. In mars, `[models]` aliases defined by packages flow through to consumers via the merge pipeline (`models-merged.json`). `[settings]` is already consumer-only. Placing visibility under `[settings]` makes the consumer-only semantics explicit and follows the universal pattern across package managers:
- **Cargo:** `[patch]`, `[profile]` are workspace-only, ignored in deps
- **Go:** `replace`, `exclude` directives are main-module-only, stripped when consumed
- **Python:** `[tool.*]` is consumer-specific config, separate from `[project]` metadata
- **Gradle:** Resolvable configurations are explicitly non-consumable

This also eliminates implementation complexity: no custom deserializer needed to strip `visibility` from the `[models]` IndexMap, no reserved alias name collision, no `#[serde(skip)]` + post-deserialization pass. Serde handles `[settings.model_visibility]` natively.

**Rejected:**
- `[models.visibility]` — `[models]` flows through deps, creating ambiguity about whether a dep's visibility config propagates. Also requires custom deserialization to separate visibility from alias entries.
- Top-level `[model_visibility]` — orphaned section with no clear grouping.

## D4: CLI flags override config entirely, not merge

**Decision:** When `--include` or `--exclude` CLI flags are present on `mars models list`, they completely replace any `[models.visibility]` config. No merging.

**Reasoning:** Consistent with the project's config precedence principle (CLI > config). Merging creates confusing interactions — "I passed `--include gpt-*` but some GPT models are hidden because config has `exclude = ["gpt-4"]`" is a bad UX. Override-not-merge is how every other CLI flag works in this project.

## D5: Filtering function lives in `models/mod.rs`, not in CLI layer

**Decision:** Create a `filter_by_visibility(aliases: &IndexMap<String, ResolvedAlias>, visibility: &VisibilityConfig) -> IndexMap<String, ResolvedAlias>` function in the models module.

**Reasoning:** The filtering logic is model-domain logic (glob matching against alias names), not CLI formatting logic. Placing it in `models/mod.rs` makes it testable without CLI scaffolding and reusable if other commands need the same filter (e.g., a future `models export`).

## D6: Load visibility separately from alias merging

**Decision:** Load visibility from `config::load().settings.model_visibility` in `run_list()`, separate from `load_merged_aliases()`. No refactoring of `load_merged_aliases` needed.

**Reasoning:** With visibility under `[settings]` instead of `[models]`, visibility and alias merging are fully independent concerns. `load_merged_aliases` stays unchanged — it loads aliases from builtins + deps + consumer config. Visibility is read from settings in `run_list()` only. The double config parse is acceptable (config loading is cheap, happens once per command invocation) and keeps the code simpler than threading visibility through the alias merge pipeline.

## D7: Validate include/exclude mutual exclusivity at config load time

**Decision:** Validate that `include` and `exclude` are mutually exclusive in `VisibilityConfig::validate()`, called during config loading — not deferred to command execution.

**Reasoning:** Fail-fast. A user with both set in their config file should see the error on any `mars models list` invocation, not silently have one win. This matches how `validate_filter` works for `FilterConfig` — validation at load time, not use time.
