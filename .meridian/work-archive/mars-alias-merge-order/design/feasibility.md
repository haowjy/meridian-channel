# Feasibility Record

## Validated Assumptions

### F-1: `EffectiveConfig.dependencies` preserves declaration order
**Verdict: CONFIRMED**

`Config.dependencies` is `IndexMap<SourceName, InstallDep>` (line 16 of config/mod.rs). `IndexMap` preserves insertion order. TOML deserialization into `IndexMap` preserves key order. `merge_with_root` iterates `config.dependencies` in order and builds `EffectiveConfig.dependencies` as another `IndexMap`. Declaration order is available throughout the pipeline.

### F-2: Topological sort breaks sibling ties alphabetically
**Verdict: CONFIRMED**

`topological_sort()` (resolve/mod.rs:617-692) explicitly sorts the initial queue alphabetically (`sorted_queue.sort()` at line 656) and sorts newly-eligible dependents alphabetically (`sorted_dependents.sort()` at line 667). The test `topo_sort_no_deps` (line 2163) asserts `["a", "b"]` for independent nodes, confirming alphabetical determinism.

### F-3: `merge_model_config` uses first-in-slice-wins
**Verdict: CONFIRMED**

The function (models/mod.rs:796-843) iterates `deps` slice in order. Uses `dep_provided` HashSet to track which aliases have been set. On conflict, skips the later dep's value and emits a warning. The first-wins contract is correct and does not need modification.

### F-4: `ResolvedGraph` does not carry declaration order
**Verdict: CONFIRMED**

`ResolvedGraph` has `order: Vec<SourceName>` (topo order) and `nodes: IndexMap<SourceName, ResolvedNode>`. Neither field records declaration position from `mars.toml`. The graph struct is general-purpose and should remain so.

### F-5: `finalize` duplicates the `dep_models` construction
**Verdict: CONFIRMED**

`finalize()` (sync/mod.rs:538-552) builds `dep_models` identically to `resolve_graph()` (sync/mod.rs:231-245), iterating `graph.order`. Both call sites must use the same declaration-ordered construction to stay consistent.

### F-6: Transitive dep sponsor resolution is needed
**Verdict: CONFIRMED**

When dep A lists transitive dep D, and dep B lists transitive dep E, and both D and E define alias `fast`, we need to know that D's declaration position comes from A and E's from B. The resolver records `required_by` in `PendingSource` but this doesn't survive into `ResolvedGraph`. However, `ResolvedNode.deps` records the dependency edges — we can walk these to find the root sponsor.

### F-7: `warn_with_context` is adequate for improved warnings
**Verdict: CONFIRMED**

`DiagnosticCollector.warn_with_context()` takes `(code, message, context)`. The current call (models/mod.rs:821-828) uses code `"model-alias-conflict"` with a message that says "and earlier dependency" without naming it. The function is flexible enough to accommodate a better message string — no structural change needed to the diagnostics system.

## Open Questions

### Q-1: Should transitive deps inherit their sponsor's declaration position?
**Decision: YES**

Without this, transitive deps would have no declaration position and would fall back to some arbitrary ordering. The sponsor-inheritance approach matches the issue spec's "recursive property" requirement: each package controls its own deps' priority.

### Q-2: What if a transitive dep is reachable from multiple direct deps?
**Decision: Use earliest sponsor**

If transitive dep D is reachable from both direct dep A (position 0) and direct dep B (position 1), D gets position 0. This is consistent with first-wins — the earlier sponsor's subtree gets priority.
