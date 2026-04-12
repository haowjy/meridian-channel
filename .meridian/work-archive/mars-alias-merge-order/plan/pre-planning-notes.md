# Pre-Planning Notes

## Key Observations from Code Probing

1. **Kahn's reference implementation exists** at `src/resolve/mod.rs:621-692`. Uses `HashMap<SourceName, usize>` for in-degree, `HashMap<SourceName, Vec<SourceName>>` for adjacency, `VecDeque` as queue with alphabetical sort. New local Kahn's should mirror this structure but use `BinaryHeap` (or sorted insertion) with `(decl_pos, name)` key.

2. **`ResolvedNode.deps`** (line 48 of resolve/mod.rs) is `Vec<SourceName>` — the edges we walk for sponsor computation and for Kahn's adjacency. Same edges as topological_sort uses.

3. **`ResolvedGraph.nodes`** is `IndexMap<SourceName, ResolvedNode>` — can iterate all nodes for building in-degree/adjacency.

4. **Two identical call sites confirmed**: `resolve_graph` lines 231-245 and `finalize` lines 538-552. Identical filter_map logic. R-1 extraction is straightforward.

5. **`merge_model_config`** (models/mod.rs:796-843): `dep_provided` is `HashSet<String>`. Changing to `HashMap<String, String>` (alias → winning dep source_name) is internal — signature unchanged.

6. **Warning uses `diag.warn_with_context`** with code `"model-alias-conflict"`. Current message: `"model alias \`{name}\` defined by both \`{dep.source_name}\` and earlier dependency — using earlier definition"`. Just needs winning dep name and resolution suggestion added.

7. **Existing sync tests** start at line 740. Have `TestFixture` helper. Tests for the new ordering will need to construct `ResolvedGraph` + `EffectiveConfig` with declaration-ordered deps and verify `declaration_ordered_dep_models` output order.

8. **Existing model tests** start at line 973. Currently no test for `merge_model_config` conflict behavior — new tests go here.

9. **No `BinaryHeap` import currently** in sync/mod.rs. Will need `std::collections::BinaryHeap` (or use a sorted Vec approach). Note: Rust's `BinaryHeap` is max-heap; need `Reverse` wrapper or custom `Ord` for min-heap behavior.

10. **`EffectiveConfig.dependencies`** is `IndexMap<SourceName, InstallDep>` — iteration order = declaration order. `config.dependencies.iter().enumerate()` gives `(position, (name, dep))`.

## Leaf Distribution Hypothesis

- **Phase 1**: S-ORDER-1, S-ORDER-2, S-ORDER-3, S-ORDER-4, S-DETERM-1, S-FINALIZE-1, S-COMPAT-2 — all ordering-related, centered on `declaration_ordered_dep_models` in sync/mod.rs + R-1 extraction
- **Phase 2**: S-WARN-1, S-WARN-2, S-WARN-3, S-COMPAT-1 — all warning-related, centered on `merge_model_config` in models/mod.rs

Could also be single phase since changes are small (~50 lines total). But two phases keeps concerns separated and allows independent testing.

## Constraints

- Repo is `mars-agents` at `/home/jimyao/gitrepos/mars-agents/`, not `meridian-cli`
- Rust codebase — `cargo build`, `cargo test`, `cargo clippy`
- `src/cli/check.rs` has unstaged changes (not ours — shared workspace, don't touch)
