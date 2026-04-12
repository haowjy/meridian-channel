# Decision Log

## D-1: Post-process ordering vs. modify topological sort

**Decision:** Post-process in `sync::resolve_graph` rather than injecting declaration order into `topological_sort`.

**Reasoning:** `topological_sort` is a general-purpose graph utility used for item discovery, collision detection, and other ordering-sensitive operations beyond model merging. Its alphabetical tiebreak is correct and desirable for those uses — deterministic and predictable. Model merge ordering is sync-pipeline-specific policy. Keeping it in `sync/mod.rs` minimizes blast radius and avoids coupling a general utility to a specific use case.

**Alternative rejected:** Option A (add `declaration_order` parameter to `topological_sort`). This would thread model-merge concerns through a general-purpose function that doesn't need them, and would change the ordering of everything that uses topo sort — not just model merging.

## D-2: Stable sort on declaration position vs. custom merge iterator

**Decision:** Use `stable_sort_by_key` on the topo-ordered dep_models vec, keyed by root sponsor's declaration position.

**Reasoning:** `merge_model_config` is first-wins, so we only need earlier-declared deps to appear first in the slice. Stable sort preserves topo order within same-position groups (so deps still precede their dependents). This is 3-4 lines of code vs. a custom iterator with reachability tracking.

**Alternative rejected:** Building a declaration-aware comparator that checks reachability between pairs. This is O(n²) in comparisons and requires precomputed transitive closure — overkill for the typical dep tree size, and harder to verify correct.

## D-3: Improve warning message in `merge_model_config` itself

**Decision:** Track which dep first provided each alias inside `merge_model_config` and include both names in the warning.

**Reasoning:** The function already has the information (it knows the current dep name and that the alias was previously set). It just needs a `HashMap<String, String>` to remember *which* dep set it. The warning improvement is self-contained — no signature change, no upstream work needed.

**Constraint discovered:** The current warning says "and earlier dependency" without naming the winner. This is because `dep_provided` is a `HashSet<String>` (alias names only), not a `HashMap<String, String>` (alias → winning dep name). Changing to a HashMap gives us both capabilities.

## D-4: Revised from stable sort to local Kahn's variant (post-review)

**Decision:** Replace the stable-sort approach (D-2) with a local Kahn's algorithm variant in `sync/mod.rs` that uses declaration position as its tiebreak.

**Reasoning:** Review (p1577) identified a critical flaw in D-2: `stable_sort_by_key` can reorder nodes across different declaration-position groups, breaking topological order in diamond dependency patterns. Example: if direct deps A (pos 0) and B (pos 1) share transitive dep D, and D has a node E that depends on it, stable sort could move D ahead of E's other dependencies. Kahn's algorithm naturally prevents this — a node is only processed when all its deps are already processed, regardless of declaration position.

**What changed from D-2:** The algorithm, not the location. The function still lives in `sync/mod.rs` as `declaration_ordered_dep_models`, still keeps `topological_sort` in `resolve/mod.rs` unchanged. Only the internal algorithm changed from "topo order + stable sort" to "re-run Kahn's with declaration-order tiebreak."

**Alternative rejected (again):** Modifying the existing `topological_sort` to accept a tiebreak parameter. Same rationale as D-1 — it's a general-purpose utility that shouldn't know about model merge policy. The local Kahn's variant in sync is ~25 lines and purpose-built.
