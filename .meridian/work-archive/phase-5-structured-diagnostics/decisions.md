# Phase 5 Decision Log

## D1: Accepted scope expansion into A2/A4 territory

**What:** The coder implementing A5 (Structured Diagnostics) also implemented significant parts of A2 (LocalPackage) and A4 (Shared Reconciliation). Specifically:
- Deleted `self_package.rs` and moved local package injection into `build_target()` 
- Added `SourceOrigin` and `Materialization` enums to `types.rs`
- Created `reconcile/` module with `fs_ops.rs`
- Changed lock building to remove `SelfLockItem` parameter

**Why accepted:** The changes are deeply intertwined — moving local package handling into `build_target()` is where diagnostics naturally thread, and the old `inject_self_items()` post-plan mutation pattern was already identified as an antipattern in the A2 design. All 28 integration tests + 360 unit tests pass. Reverting would require expensive untangling with high risk of regressions.

**Alternatives rejected:** Reverting out-of-scope changes and redoing only A5 — too risky given how intertwined the changes are, and the coder's approach is actually correct per the design.

**Impact:** Future A2 and A4 phases should note that significant portions of their work are already done. The reconcile module API should be reviewed as part of A4 to ensure it matches the design spec.

## D2: Fixed diagnostic level rendering in human mode

**What:** The coder's implementation hardcoded all diagnostics as yellow "warning:" in human mode. Fixed to use `Diagnostic::Display` impl and vary color by level (yellow for Warning, cyan for Info).

**Why:** No Info diagnostics exist yet, but the rendering would be wrong the moment one is added. Fix is trivial and prevents a future bug.
