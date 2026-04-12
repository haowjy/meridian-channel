# Model Alias Merge Order — Architecture

## Problem Anatomy

The data flows through three stages:
1. `EffectiveConfig.dependencies` (IndexMap — preserves declaration order from `mars.toml`)
2. `resolve()` → `ResolvedGraph.order` (topological sort — deps before dependents, alphabetical for siblings)
3. `resolve_graph()` iterates `graph.order` to build `dep_models: Vec<ResolvedDepModels>` → passed to `merge_model_config()`

Declaration order is available in stage 1 but lost at stage 2. The fix must re-introduce declaration order as a tiebreaker for siblings at stage 2→3.

## Approach: Declaration-Ordered Kahn's Variant in sync/mod.rs

**Do not modify `topological_sort` or `ResolvedGraph.order`.** The topo sort is correct for its purpose (ensuring deps are processed before dependents for item discovery, collision detection, etc.). Its alphabetical tiebreak is correct and desirable for those uses.

Model merge needs a different ordering that respects both constraints:
- Dependencies before dependents (topological property)
- Siblings ordered by declaration order (from `mars.toml`)

### Rejected approach: stable sort

The initial design considered `stable_sort_by_key` on the topo-ordered dep_models, keyed by root sponsor declaration position. **This is incorrect.** Stable sort preserves relative order of equal-key elements, but it can reorder elements across different key groups — moving a node with key=0 ahead of one with key=1 even when a dependency edge exists between them. This breaks the topological invariant in diamond dependency patterns.

### Chosen approach: Local Kahn's with declaration-order tiebreak

Build a Kahn's-algorithm variant inside `sync/mod.rs` that:
1. Uses the same dependency edges as the graph
2. Replaces the alphabetical tiebreak with declaration-order tiebreak
3. Is scoped to the sync module — the existing `topological_sort` in `resolve/mod.rs` stays untouched

This is ~25 lines. It provably maintains topological order while giving declaration order control over sibling ordering. The Kahn's algorithm naturally handles all the edge cases (diamonds, shared transitive deps) because it only processes a node when all its dependencies are already processed.

### Declaration position assignment

Each node needs a declaration position for the tiebreak comparator:

1. **Direct deps**: Position = index in `EffectiveConfig.dependencies` iteration order (0, 1, 2, ...)
2. **Transitive deps**: Position = lowest (earliest) declaration position among all direct deps that transitively reach this node. Walk from each direct dep downward through `ResolvedNode.deps` to find reachable transitive deps.
3. **Secondary tiebreak**: When two nodes share the same declaration position (e.g., two transitive deps under the same sponsor), break ties alphabetically for determinism.

### Why "earliest sponsor" is correct

If transitive dep D is reachable from both direct dep A (position 0) and direct dep B (position 1), assigning D position 0 means D's model definitions are processed with A's subtree. This is consistent with first-wins semantics: the user listed A first, so A's entire dependency subtree gets priority.

## Detailed Design

### New function: `declaration_ordered_dep_models`

Location: `src/sync/mod.rs` (private helper)

```rust
fn declaration_ordered_dep_models(
    graph: &ResolvedGraph,
    config: &EffectiveConfig,
) -> Vec<crate::models::ResolvedDepModels>
```

**Algorithm:**

1. **Compute declaration positions:**
   - Iterate `config.dependencies` to build `decl_pos: HashMap<SourceName, usize>` for direct deps
   - For each direct dep, BFS/DFS through `graph.nodes[dep].deps` recursively to find all transitive deps. Assign each transitive dep the minimum declaration position among all sponsors that reach it.

2. **Kahn's with declaration-order tiebreak:**
   - Build in-degree and adjacency from `graph.nodes` (same structure as `topological_sort`)
   - Initialize: collect nodes with in_degree == 0 into a `BinaryHeap` (min-heap) ordered by `(decl_pos, name)` — declaration position primary, alphabetical secondary
   - Process: pop min, emit, decrement dependents' in-degree, push newly-zero-in-degree nodes
   - Result: `Vec<SourceName>` in topological order with declaration-order sibling tiebreak

3. **Filter and collect:**
   - From the ordered names, filter to nodes with non-empty `manifest.models`
   - Build `Vec<ResolvedDepModels>` from filtered entries

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

Same replacement — `finalize` builds `dep_models` identically and must use the same ordering for S-FINALIZE-1. Both call the same helper, eliminating code duplication (R-1).

### Improved conflict warning in `merge_model_config`

Current warning says `"and earlier dependency"` without naming the winner. The function doesn't track which dep first provided each alias.

Change: replace `dep_provided: HashSet<String>` with `dep_provided: HashMap<String, String>` that maps alias name → winning dep's source name. On conflict:

```
model alias `fast` defined by both `workflow-a` (declared first) and `workflow-b` — using workflow-a
  → add [models.fast] to your mars.toml to resolve explicitly
```

This change is internal to `merge_model_config` — its signature and first-wins contract are unchanged.

## Files Changed

| File | Change |
|---|---|
| `src/sync/mod.rs` | Add `declaration_ordered_dep_models()` helper with local Kahn's variant; use it in `resolve_graph` and `finalize` |
| `src/models/mod.rs` | Change `dep_provided` from `HashSet` to `HashMap`; improve conflict warning message to name both deps and suggest override |
| `src/models/mod.rs` (tests) | Add tests: sibling conflict names both deps, consumer override suppresses warning |
| `src/sync/mod.rs` (tests) | Add tests: declaration-ordered merge for siblings, diamonds, transitive sponsor inheritance |

## What Doesn't Change

- `merge_model_config` signature and first-wins contract
- `topological_sort` function in `resolve/mod.rs`
- `ResolvedGraph` struct
- `resolve()` function in `src/resolve/mod.rs`
- `models-merged.json` format
- Any CLI commands or config surface

## Edge Cases

### Diamond dependency
Direct deps A (pos 0) and B (pos 1) both depend on D. D gets position 0 (earliest sponsor). D is processed before both A and B in the merge (deps before dependents), which is correct — D's aliases can be overridden by A or B.

### Three-way alias conflict
Deps A (pos 0), B (pos 1), C (pos 2) all define alias `fast`. A wins. Two warnings emitted: one for B vs A, one for C vs A.

### Dep is both direct and transitive
If A is listed in `[dependencies]` and also appears in B's transitive deps, A's declaration position comes from its direct listing (position in `config.dependencies`), which is always present and correct.

### Deep transitive chains
BFS from each direct dep is O(V+E) total. For typical dependency trees (< 100 nodes), this is negligible. No performance concern.
