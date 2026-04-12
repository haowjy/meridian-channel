# Leaf Ownership Ledger

| EARS ID | Summary | Owning Phase | Status | Tester Lane | Evidence Pointer |
|---|---|---|---|---|---|
| S-ORDER-1 | Direct sibling conflicts use consumer declaration order. | Phase 1 | planned | `@unit-tester`, `@smoke-tester` | — |
| S-ORDER-2 | Transitive sibling conflicts use the declaring package's manifest order. | Phase 1 | planned | `@unit-tester` | — |
| S-ORDER-4 | Shared transitive deps inherit the earliest sponsor position. | Phase 1 | planned | `@unit-tester` | — |
| S-ORDER-3 | Dependents still override their own dependencies. | Phase 1 | planned | `@unit-tester`, `@smoke-tester` | — |
| S-WARN-1 | Two-way conflict warning names both winner and loser and suggests explicit override. | Phase 2 | planned | `@unit-tester`, `@smoke-tester` | — |
| S-WARN-2 | Consumer override suppresses dependency-conflict warning. | Phase 2 | planned | `@unit-tester` | — |
| S-DETERM-1 | Dependency ordering stays deterministic for identical input graphs. | Phase 1 | planned | `@unit-tester`, `@verifier` | — |
| S-COMPAT-1 | Conflicts remain warnings and do not block sync. | Phase 2 | planned | `@smoke-tester`, `@verifier` | — |
| S-WARN-3 | Three-way conflicts emit one warning per losing dependency. | Phase 2 | planned | `@unit-tester`, `@smoke-tester` | — |
| S-COMPAT-2 | `models-merged.json` format stays unchanged. | Phase 1 | planned | `@smoke-tester`, `@verifier` | — |
| S-FINALIZE-1 | `finalize()` uses the same declaration-aware dependency ordering as `resolve_graph()`. | Phase 1 | planned | `@unit-tester`, `@smoke-tester` | — |
