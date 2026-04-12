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
