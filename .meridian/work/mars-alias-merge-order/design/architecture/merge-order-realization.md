# Model Alias Merge Order — Architecture

## Problem Anatomy

The data flows through three stages:
1. `EffectiveConfig.dependencies` (IndexMap — preserves declaration order from `mars.toml`)
2. `resolve()` → `ResolvedGraph.order` (topological sort — deps before dependents, alphabetical for siblings)
3. `resolve_graph()` iterates `graph.order` to build `dep_models: Vec<ResolvedDepModels>` → passed to `merge_model_config()`

Declaration order is available in stage 1 but lost at stage 2. The fix must re-introduce declaration order as a tiebreaker for siblings at stage 2→3.

## Approach: Declaration-Ordered Model Merge Iterator

**Do not modify `topological_sort` or `ResolvedGraph.order`.** The topo sort is correct for its purpose (ensuring deps are processed before dependents). Model merge needs a different ordering that respects both constraints:
- Dependencies before dependents (from topo sort)
- Siblings ordered by declaration order (from `mars.toml`)

### Key insight

We need a new ordering function that produces a model-merge-specific iteration order. This function:
1. Takes the `ResolvedGraph` (for dependency relationships and topo order)
2. Takes the `EffectiveConfig` (for declaration order)
3. Returns `Vec<SourceName>` ordered for model merging

### Algorithm: Declaration-Aware Stable Sort

The simplest correct approach is to take the topological order and re-sort siblings (nodes at the same "depth" or with no dependency relationship) by their declaration order. But "depth" is imprecise in a DAG — two nodes at the same depth can still have a dependency relationship.

**Better formulation**: Given the topological order, for any two nodes A and B where neither depends on the other (directly or transitively), sort by declaration order. For nodes where one depends on the other, preserve topo order (dep first).

**Implementation**: 

1. Build a reachability set from `ResolvedGraph.nodes` — for each node, compute the set of all transitive dependencies.
2. Build a declaration-order index from `EffectiveConfig.dependencies` — maps each direct dep name to its position in the `[dependencies]` section.
3. For transitive deps (not directly in `mars.toml`), derive their declaration position from their "sponsor" — the direct dep that transitively requires them.
4. Stable-sort the topological order using a comparator that:
   - Preserves topo order when one node depends on the other
   - Uses declaration position when nodes are siblings

**Simplification**: The stable sort doesn't need reachability checks if we use a different framing. The topological order already guarantees deps come before dependents. We only need to re-order *within each set of nodes that are simultaneously eligible* (same in-degree reduction round in Kahn's). This is exactly where the alphabetical tiebreak happens.

### Refined Algorithm: Inject Declaration Order Into Kahn's Tiebreak

Instead of post-processing, inject the declaration order directly into the topological sort's tiebreak logic. Currently:

```rust
// In topological_sort():
let mut sorted_queue: Vec<SourceName> = queue.drain(..).collect();
sorted_queue.sort();  // ← alphabetical tiebreak
queue.extend(sorted_queue);
```

Replace the alphabetical sort with a declaration-order-aware sort. But `topological_sort` doesn't have access to declaration order. Two options:

**Option A: Add `declaration_order` to `ResolvedGraph`**
- Store declaration positions in `ResolvedGraph` during `resolve()`
- Pass to `topological_sort()` as a tiebreak comparator
- Topo sort uses declaration order for same-in-degree nodes

**Option B: Post-process in `resolve_graph` (sync phase 2)**
- Keep `topological_sort` unchanged
- After getting `graph.order`, build the model-merge ordering in `sync::resolve_graph`
- Use a separate function that walks the topo order but re-sorts siblings by declaration order

### Recommended: Option B (Post-process)

**Rationale:**
- `topological_sort` is a general-purpose graph utility — it shouldn't know about model merge concerns
- The alphabetical tiebreak in topo sort is correct and desirable for other uses (deterministic graph ordering for item discovery, collision detection, etc.)
- The model merge ordering is sync-pipeline-specific policy; keep it in `sync/mod.rs`
- Minimal blast radius — only the model merge code path changes

## Detailed Design

### New function: `declaration_ordered_dep_models`

Location: `src/sync/mod.rs` (private helper)

```
fn declaration_ordered_dep_models(
    graph: &ResolvedGraph,
    config: &EffectiveConfig,
) -> Vec<ResolvedDepModels>
```

**Behavior:**
1. Build `decl_index: HashMap<SourceName, usize>` from `config.dependencies` iteration order (direct deps get their declaration position)
2. For transitive deps not in `config.dependencies`, assign them the declaration position of their "root sponsor" — the direct dep that transitively requires them. Walk `graph.nodes[name].deps` upward to find the direct dep ancestor. If a transitive dep is reachable from multiple direct deps, use the earliest (lowest position) sponsor.
3. Build the output `Vec<ResolvedDepModels>` by iterating `graph.order` but sorting siblings by their declaration position (primary) and name (secondary, for determinism within same sponsor).
4. Filter to nodes that have non-empty model configs (same filter as current code).

**Alternative simpler implementation**: Since `merge_model_config` is first-wins, we only need to ensure that among siblings, earlier-declared deps appear first in the slice. We can:
1. Collect all dep models entries
2. Stable-sort by declaration position of their root sponsor
3. The stable sort preserves topo order within the same position group

This is simpler because `stable_sort_by_key` does exactly what we need — it preserves the relative order of elements with equal keys (topo order) while sorting by the key (declaration position).

### Changes to `resolve_graph` (sync phase 2)

Replace:
```rust
let dep_models: Vec<crate::models::ResolvedDepModels> = graph
    .order
    .iter()
    .filter_map(|name| { ... })
    .collect();
```

With:
```rust
let dep_models = declaration_ordered_dep_models(&graph, &loaded.effective);
```

### Changes to `finalize` (sync phase 7)

Same replacement — `finalize` builds `dep_models` identically and must use the same ordering for S-FINALIZE-1.

### Improved conflict warning in `merge_model_config`

Current warning says `"and earlier dependency"` without naming it. The function doesn't track which dep first provided the alias.

Change: add a `first_provider: HashMap<String, String>` that records which dep first set each alias. On conflict, the warning becomes:

```
model alias `fast` defined by both `workflow-a` (declared first) and `workflow-b` — using workflow-a
  → add [models.fast] to your mars.toml to resolve explicitly
```

This change is internal to `merge_model_config` — its signature and first-wins contract are unchanged.

## Files Changed

| File | Change |
|---|---|
| `src/sync/mod.rs` | Add `declaration_ordered_dep_models()` helper; use it in `resolve_graph` and `finalize` |
| `src/models/mod.rs` | Improve conflict warning message to name both deps and suggest override |
| `src/models/mod.rs` (tests) | Add tests for sibling conflict with declaration-order tiebreak |
| `src/sync/mod.rs` (tests) | Add tests for declaration-ordered model merge |

## What Doesn't Change

- `merge_model_config` signature and first-wins contract
- `topological_sort` function
- `ResolvedGraph` struct
- `resolve()` function in `src/resolve/mod.rs`
- `models-merged.json` format
- Any CLI commands or config surface
