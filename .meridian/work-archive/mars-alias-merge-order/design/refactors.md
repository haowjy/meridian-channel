# Refactor Agenda

## R-1: Extract `dep_models` construction into shared helper

**Current state:** `resolve_graph` (lines 231-245) and `finalize` (lines 538-552) contain duplicated code that builds `Vec<ResolvedDepModels>` from `graph.order`. Both iterate the same way with the same filter logic.

**Target state:** A single function `declaration_ordered_dep_models(graph, config)` replaces both. This also prevents the new declaration-order logic from being duplicated.

**Sequencing:** Must happen in the same change as the ordering fix, since extracting the helper and changing its ordering are the same edit.

**Risk:** Low. The two call sites are nearly identical. The only difference is that `finalize` uses a `&` reference to `graph` from nested state while `resolve_graph` owns it. Both can call the same function with `&ResolvedGraph`.
