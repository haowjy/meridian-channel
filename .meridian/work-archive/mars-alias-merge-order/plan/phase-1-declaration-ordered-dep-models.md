# Phase 1: Declaration-Ordered Dependency Model Construction

## Round

1 (parallel with Phase 2)

## Scope

Implement the declaration-order-aware dependency model traversal in `/home/jimyao/gitrepos/mars-agents/src/sync/mod.rs`, extract the shared `dep_models` builder required by R-1, and route both `resolve_graph()` and `finalize()` through the same helper. This phase owns ordering semantics and sync/finalize consistency.

## Boundaries

- Modify only the sync-layer implementation and tests needed to prove declaration-order behavior.
- Keep `/home/jimyao/gitrepos/mars-agents/src/resolve/mod.rs` unchanged; `topological_sort()` remains the general-purpose resolver order.
- Do not change warning wording, winner attribution text, or consumer-override suppression rules in `merge_model_config()`; those belong to Phase 2.

## Touched Files and Modules

- `/home/jimyao/gitrepos/mars-agents/src/sync/mod.rs`
- Read-only reference: `/home/jimyao/gitrepos/mars-agents/src/resolve/mod.rs`

## Claimed EARS Statement IDs

- S-ORDER-1
- S-ORDER-2
- S-ORDER-3
- S-ORDER-4
- S-DETERM-1
- S-COMPAT-2
- S-FINALIZE-1

## Touched Refactor IDs

- R-1

## Dependencies

- None

## Tester Lanes

- `@verifier`: run focused build, lint, and targeted test verification for `src/sync/mod.rs`.
- `@unit-tester`: add or expand graph-shape tests for sibling order, sponsor inheritance, diamond handling, and deterministic secondary tiebreak behavior.
- `@smoke-tester`: run a real `cargo run -- sync` fixture in `/home/jimyao/gitrepos/mars-agents/` and confirm runtime merge order and persisted `models-merged.json` use the same dependency ordering.

## Exit Criteria

- `declaration_ordered_dep_models(graph, config)` exists in `src/sync/mod.rs` and is the only `dep_models` construction path used by both `resolve_graph()` and `finalize()`.
- Direct sibling alias conflicts resolve by consumer declaration order rather than alphabetical topo tie order.
- Transitive dependency sponsor inheritance uses the earliest reachable direct dependency as the declaration position source.
- Dependency-before-dependent ordering remains intact for shared transitive and diamond patterns.
- Nodes with identical declaration positions use a deterministic alphabetical secondary tiebreak.
- `models-merged.json` persistence uses the same dependency ordering as `resolve_graph()`, with unchanged JSON shape.

## Verification Commands

- `cargo build`
- `cargo test sync::`
- `cargo run -- sync`

## Risks to Watch

- Reintroducing a sort that violates topological ordering across sponsor groups.
- Letting `resolve_graph()` and `finalize()` drift back into separate ordering implementations.
- Treating transitive deps without a direct sponsor mapping and silently falling back to arbitrary order.
