# Feasibility Analysis

This document records validated assumptions and probe evidence grounding the design.

## Validated Assumptions

### FA-001: Test Independence
**Assumption:** Tests in the resolver module do not depend on module-private state that would prevent extraction to a separate `tests/` directory.

**Evidence:** Reviewed test structure at lines 1541-4464. Tests use:
- `super::*` imports for types and functions
- `MockProvider` helper defined within test module
- Helper functions (`make_config`, `git_spec`, etc.) defined within test module
- `tempfile::TempDir` for filesystem fixtures

**Verdict:** CONFIRMED. Tests can be extracted. The `MockProvider` and helpers move with them.

### FA-002: Context Parameter Consolidation
**Assumption:** The 11+ mutable parameters to `resolve_package_bottom_up` can be consolidated into a single `&mut ResolverContext` without changing call patterns.

**Evidence:** Signature analysis of `resolve_package_bottom_up`:
```rust
fn resolve_package_bottom_up(
    pending_src: &PendingSource,
    seed_items: bool,
    provider: &dyn SourceProvider,
    locked: Option<&LockFile>,
    options: &ResolveOptions,
    diag: &mut DiagnosticCollector,
    registry: &mut IndexMap<SourceName, RegisteredPackage>,
    package_states: &mut HashMap<SourceName, PackageResolutionState>,
    id_index: &mut HashMap<SourceId, SourceName>,
    constraints: &mut HashMap<SourceName, Vec<(String, VersionConstraint)>>,
    filter_constraints: &mut HashMap<SourceName, Vec<FilterMode>>,
    stack: &mut Vec<PendingItem>,
) -> Result<(), MarsError>
```

Parameters fall into two categories:
1. **Read-only context:** `pending_src`, `seed_items`, `provider`, `locked`, `options`, `diag`
2. **Mutable state:** `registry`, `package_states`, `id_index`, `constraints`, `filter_constraints`, `stack`

The mutable state parameters are always passed together from `resolve()` and never partially. They can be grouped into `ResolverContext`.

**Verdict:** CONFIRMED. Consolidation is mechanical.

### FA-003: Constraint/Filter Separation
**Assumption:** `constraints` and `filter_constraints` serve different purposes and can be cleanly separated without behavioral regression (before fixing the bug).

**Evidence:** Usage analysis:
- `constraints` (version constraints):
  - Used in `resolve_git_source()` for version selection
  - Used in `validate_all_constraints()` for post-resolution validation
  - Used in `resolve_skill_ref()` for constraint lookup
- `filter_constraints`:
  - Accumulated from request filters
  - Used in `is_item_excluded()` for traversal decisions
  - Returned in `ResolvedGraph.filters` for sync phase

They are already separate variables in `resolve()`. The bug is that filtered requests sometimes skip resolution, not that the data structures are conflated.

**Verdict:** CONFIRMED. Renaming to `version_constraints` and `materialization_filters` is documentation, not restructuring.

### FA-004: Skill Resolution Order
**Assumption:** Skill resolution currently uses insertion order and can be changed to dependency closure order without breaking existing behavior that doesn't rely on the bug.

**Evidence:** Current `resolve_skill_ref()` at line 1089:
```rust
for (package_name, package) in registry {  // IndexMap iteration = insertion order
    if package_name == &requester.package {
        continue;
    }
    if !package.has_skill(skill) {
        continue;
    }
    // returns first match
}
```

To fix, we need to:
1. Compute dependency closure from `registry` (each `RegisteredPackage` has `node.deps`)
2. Iterate in topological order (dependencies before dependents)

**Verdict:** CONFIRMED. The deps information is already available in `ResolvedNode.deps`. Computing closure is straightforward BFS/DFS.

### FA-005: Latest Validation
**Assumption:** The `validate_all_constraints()` short-circuit for Latest can be removed without breaking valid use cases.

**Evidence:** Current code at line 1509:
```rust
if has_latest {
    continue;  // skips entire package validation
}
```

This was likely added to avoid false positives when Latest resolves to a version that doesn't match explicit semver constraints. But it masks the real bug: if a package has both Latest and `^1.0` constraints, and resolves to v2.0.0, that should be an error.

**Verdict:** CONFIRMED. Removing the short-circuit and validating correctly is the fix, not a breaking change.

## Open Questions

### OQ-001: Sync Phase Filter Handling
**Question:** Does the sync phase correctly handle the accumulated filters from `ResolvedGraph.filters`?

**Current understanding:** `target.rs` line 78-84:
```rust
let filters = graph
    .filters
    .get(source_name)
    .filter(|filters| !filters.is_empty())
    .cloned()
    .or_else(|| source_config.map(|source| vec![source.filter.clone()]))
    .unwrap_or_else(|| vec![FilterMode::All]);
```

It falls back to config filter if graph filter is empty. This seems correct — graph.filters is accumulated during resolution, config filter is the direct declaration.

**Action:** No blocking issue. The fix in resolver (separating constraints from filters) should not require sync changes.

### OQ-002: RegisteredPackage Lifetime
**Question:** Is `RegisteredPackage` ever needed after `resolve()` returns?

**Current understanding:** No. It's internal to the resolver. `ResolvedGraph` is the public output, containing `ResolvedNode` which has no reference to `RegisteredPackage`.

**Action:** No blocking issue. Confirms that `RegisteredPackage` simplification (REF-015) is safe.

## Risks

### RISK-001: Hidden Test Dependencies
**Risk:** Some tests may implicitly depend on internal module structure (e.g., specific import paths).

**Mitigation:** After test extraction, run `cargo test --lib` and verify identical test count. Check for `use super::*` patterns that might break.

### RISK-002: Performance Regression from Context Indirection
**Risk:** Wrapping parameters in `ResolverContext` adds one level of indirection for every field access.

**Mitigation:** Measure with `cargo bench` if benchmarks exist. If not, trust that the Rust compiler inlines trivial accessor methods. The current parameter passing already involves indirection through references.

### RISK-003: Bug Fix Behavioral Changes
**Risk:** Bug fixes (REF-011 through REF-014) change observable behavior. Code relying on buggy behavior may break.

**Mitigation:** 
- Each bug fix should be a separate commit with clear description
- Add regression tests that demonstrate the bug before fixing
- Document expected behavior changes in commit message
