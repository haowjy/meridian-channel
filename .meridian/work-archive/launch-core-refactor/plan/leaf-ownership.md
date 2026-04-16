# R06 Leaf Ownership

No `design/spec/` EARS tree exists for this work item today. This ledger uses
the stable requirement, invariant, feasibility, and dependency IDs already
present in the design package as the executable ownership leaves for planning
and execution.

| Leaf ID | Source | Phase Owner | Status | Tester Lane | Evidence Pointer | Notes |
|---|---|---|---|---|---|---|
| `DEP-R01` | `design/refactors.md` dependency | Phase 1 | pending | `@verifier`, `@unit-tester`, `@smoke-tester` | — | Foundational prerequisite for `LaunchRuntime.project_paths`. |
| `REQ-SC1` | `requirements.md` success criteria | Phase 4 | pending | `@verifier`, `@unit-tester`, `@smoke-tester` | — | Raw factory boundary (`SpawnRequest + LaunchRuntime`). |
| `REQ-SC2` | `requirements.md` success criteria | Phase 5 | pending | `@verifier`, `@unit-tester`, `@smoke-tester` | — | Driving adapters must stop composing. |
| `REQ-SC3` | `requirements.md` success criteria | Phase 2 | pending | `@verifier`, `@unit-tester`, `@smoke-tester` | — | Persisted raw artifact must round-trip without escape hatches. |
| `REQ-SC4` | `requirements.md` success criteria | Phase 6 | pending | `@verifier`, `@unit-tester`, `@smoke-tester` | — | Behavioral factory tests replace heuristic guards. |
| `REQ-SC5` | `requirements.md` success criteria | Phase 5 | pending | `@verifier`, `@unit-tester`, `@smoke-tester` | — | Session-id observation only through the adapter seam. |
| `REQ-SC6` | `requirements.md` success criteria | Phase 6 | pending | `@verifier`, `@unit-tester`, `@smoke-tester` | — | Reviewer drift gate replaces the old script. |
| `ARCH-I1` | `design/launch-composition-invariant.md` | Phase 4 | pending | `@verifier`, `@unit-tester`, `@smoke-tester` | — | Composition centralization becomes true at the factory seam. |
| `ARCH-I2` | `design/launch-composition-invariant.md` | Phase 5 | pending | `@verifier`, `@unit-tester`, `@smoke-tester` | — | Driving-adapter prohibition list enforced behaviorally. |
| `ARCH-I3` | `design/launch-composition-invariant.md` | Phase 5 | pending | `@verifier`, `@unit-tester`, `@smoke-tester` | — | Single-owner table closes only after driver/adapter rewires. |
| `ARCH-I4` | `design/launch-composition-invariant.md` | Phase 5 | pending | `@verifier`, `@unit-tester`, `@smoke-tester` | — | One observation path, no shared adapter launch state. |
| `ARCH-I5` | `design/launch-composition-invariant.md` | Phase 2 | pending | `@verifier`, `@unit-tester`, `@smoke-tester` | — | DTO discipline tied to persisted raw artifact. |
| `ARCH-I6` | `design/launch-composition-invariant.md` | Phase 3 | pending | `@verifier`, `@unit-tester`, `@smoke-tester` | — | Stage modules own real logic. |
| `ARCH-I7` | `design/launch-composition-invariant.md` | Phase 3 | pending | `@verifier`, `@unit-tester`, `@smoke-tester` | — | Driven port remains contracts-only. |
| `ARCH-I8` | `design/launch-composition-invariant.md` | Phase 4 | pending | `@verifier`, `@unit-tester`, `@smoke-tester` | — | Executors consume context only; no composition rebuild. |
| `ARCH-I9` | `design/launch-composition-invariant.md` | Phase 3 | pending | `@verifier`, `@unit-tester`, `@smoke-tester` | — | Workspace-projection seam established before argv build. |
| `ARCH-I10` | `design/launch-composition-invariant.md` | Phase 5 | pending | `@verifier`, `@unit-tester`, `@smoke-tester` | — | Fork-after-row ordering enforced in all launch paths. |
| `ARCH-I11` | `design/launch-composition-invariant.md` | Phase 5 | pending | `@verifier`, `@unit-tester`, `@smoke-tester` | — | Fork lineage coherence across `sessions.jsonl` and `spawns.jsonl`. |
| `ARCH-I12` | `design/launch-composition-invariant.md` | Phase 5 | pending | `@verifier`, `@unit-tester`, `@smoke-tester` | — | Report extraction returns user-facing content only. |
| `ARCH-I13` | `design/launch-composition-invariant.md` | Phase 6 | pending | `@verifier`, `@unit-tester`, `@smoke-tester` | — | Silent adapter transformations must surface as warnings. |
| `FEAS-FV11` | `design/feasibility.md` | Phase 2 | pending | `@verifier`, `@unit-tester`, `@smoke-tester` | — | Raw-request factory boundary proven by shipped schema/worker artifact. |
| `FEAS-FV12` | `design/feasibility.md` | Phase 6 | pending | `@verifier`, `@unit-tester`, `@smoke-tester` | — | Drift gate wired into CI on the protected surface. |

