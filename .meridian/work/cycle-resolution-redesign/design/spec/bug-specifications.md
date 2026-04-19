# Bug Specifications

This document specifies the known bugs with behavioral evidence, root cause analysis, fix approach, and the regression tests that must land with each fix.

The behavioral contract for these fixes lives in [resolver-behavioral-contract.md](resolver-behavioral-contract.md).

---

## Bug #1: Filtered Dependency Leak

**Phase gate**
- Phase 5 / `REF-011`

### Symptoms
When a direct dependency has a filter (for example `agents = ["runner"]`), its transitive dependencies may incorrectly seed items that should not be traversed.

### Reproduction
```toml
# mars.toml
[dependencies.parent]
url = "..."
version = "v1.0.0"
agents = ["runner"]  # Only want the "runner" agent
```

```toml
# parent/mars.toml (manifest)
[dependencies.child]
url = "..."
version = "v1.0.0"
# No filter — means "all items"
```

Expected: Only `parent/runner` agent is seeded and traversed.
Actual: `child` items may be seeded because `seed_unfiltered_manifest_deps` is computed incorrectly.

### Root Cause
In `resolve_package_bottom_up()`:
```rust
let seed_unfiltered_manifest_deps = seed_items && is_unfiltered_request(&pending_src.filter);
```

This conflates "should we resolve this package's deps" with "should we seed items from this package's deps".

### Fix Approach
1. Split `constraints` into `version_constraints` for resolution and `materialization_filters` for item selection.
2. Always resolve transitive deps for version selection.
3. Seed items only when the accumulated materialization filters permit them.

### Regression Test Plan

**New test name**
- `filtered_include_dep_resolves_version_without_seeding_transitive_items`

**Test scenario**
- Setup: a direct dependency `parent` is filtered to include only `runner`; `parent` depends on `child` with no filter, and `child` exports items that would be traversed if seeded.
- Action: run resolver on the consumer config with the filtered `parent` dependency.
- Expected result: `parent` and `child` both appear in the resolved graph for version-selection purposes, but `child` items are not eagerly seeded or traversed through the filtered path.

**EARS ID**
- `REQ-FIL-001`, `REQ-FIL-002` in [resolver-behavioral-contract.md](resolver-behavioral-contract.md)

### Verification
```bash
cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml filtered_include_dep_resolves_version_without_seeding_transitive_items
```

Expected: `1/1` new regression test passes.

---

## Bug #2: Latest Disables Semver Validation

**Phase gate**
- Phase 5 / `REF-012`

### Symptoms
When a package has both a `Latest` constraint and explicit semver constraints, the semver constraints are not validated against the resolved version.

### Reproduction
```toml
# Consumer A
[dependencies.shared]
url = "..."
# version omitted = Latest
```

```toml
# Consumer B (transitive or merged)
[dependencies.shared]
url = "..."
version = "^1.0"
```

If `shared@latest` resolves to `v2.0.0`:
- Expected: Error — `v2.0.0` does not satisfy `^1.0`
- Actual: No error — validation is skipped

### Root Cause
In `validate_all_constraints()`:
```rust
if has_latest {
    continue;
}
```

That skips validation for the entire package whenever any request uses `Latest`.

### Fix Approach
1. Remove the `has_latest` short-circuit.
2. Validate each semver constraint against the resolved version.
3. Treat `Latest` as "no additional semver restriction", not "skip all validation".

### Regression Test Plan

**New test name**
- `latest_constraint_does_not_skip_sibling_semver_validation`

**Test scenario**
- Setup: two dependents reference the same package; one uses `Latest`, the other uses `^1.0`; available versions resolve `Latest` to `v2.0.0`.
- Action: run resolver and allow post-resolution validation to execute.
- Expected result: resolver emits `VersionConflict` because the resolved version selected by `Latest` does not satisfy the sibling semver constraint.

**EARS ID**
- `REQ-VAL-001`, `REQ-VAL-002` in [resolver-behavioral-contract.md](resolver-behavioral-contract.md)

### Verification
```bash
cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml latest_constraint_does_not_skip_sibling_semver_validation
```

Expected: `1/1` new regression test passes.

---

## Bug #3: Constraint Comparison Uses Syntax, Not Resolved Version

**Phase gate**
- Phase 5 / `REF-013`

### Symptoms
Two semantically equivalent constraints with different syntax are treated as conflicting.

### Reproduction
```toml
# Consumer A
[dependencies.shared]
url = "..."
version = "^1.0"
```

```toml
# Consumer B (transitive)
[dependencies.shared]
url = "..."
version = ">=1.0.0, <2.0.0"
```

Expected: Compatible when both accept the resolved version.
Actual: May be flagged as conflicting because compatibility checks compare constraint syntax.

### Root Cause
In `compat.rs`, semver compatibility is currently based on equality of `VersionReq` syntax rather than acceptance of the concrete resolved version.

### Fix Approach
1. Compare semver compatibility against the resolved version the graph selected.
2. Treat syntactically different semver expressions as compatible when they both accept that resolved version.
3. Keep hard conflicts for genuinely incompatible resolved versions.

### Regression Test Plan

**New test name**
- `equivalent_semver_syntax_accepts_same_resolved_version`

**Test scenario**
- Setup: two dependents request the same package using syntactically different but semantically equivalent semver expressions; available versions include at least one version both expressions accept.
- Action: run resolver through version selection and post-resolution validation.
- Expected result: resolver accepts the package, selects a shared resolved version, and does not raise a false constraint conflict.

**EARS ID**
- `REQ-VAL-001`, `REQ-VAL-003` in [resolver-behavioral-contract.md](resolver-behavioral-contract.md)

### Verification
```bash
cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml equivalent_semver_syntax_accepts_same_resolved_version
```

Expected: `1/1` new regression test passes.

---

## Bug #4: Skill Lookup Uses Insertion Order, Not Dependency Closure

**Phase gate**
- Phase 5 / `REF-014`

### Symptoms
Skill resolution depends on the order packages were declared in `mars.toml`, not their dependency relationships.

### Reproduction
```toml
# mars.toml
[dependencies.sibling-a]
url = "..."

[dependencies.sibling-b]
url = "..."

[dependencies.my-dep]
url = "..."
```

```markdown
<!-- my-dep/agents/coder.md -->
---
skills: [planning]
---
```

If both `sibling-a` and `my-dep` provide a `planning` skill:
- Expected: use `planning` from `my-dep` because it is in the requesting agent's dependency closure
- Actual: resolver uses whichever package appears first in insertion order

### Root Cause
`resolve_skill_ref()` searches the registry in `IndexMap` iteration order rather than same-package first plus dependency-closure order.

### Fix Approach
1. Keep same-package precedence.
2. Build a dependency closure from the requesting package using resolved dependency edges.
3. Search the closure before considering unrelated packages.

### Regression Test Plan

**New test name**
- `skill_resolution_prefers_dependency_closure_over_insertion_order`

**Test scenario**
- Setup: a requester package depends on `my-dep`, an unrelated sibling package is inserted earlier in the registry, and both export the same skill name.
- Action: resolve the requester agent's frontmatter skill reference.
- Expected result: resolver selects the skill from `my-dep`, not the unrelated earlier sibling.

**EARS ID**
- `REQ-SKL-001`, `REQ-SKL-002` in [resolver-behavioral-contract.md](resolver-behavioral-contract.md)

### Verification
```bash
cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml skill_resolution_prefers_dependency_closure_over_insertion_order
```

Expected: `1/1` new regression test passes.

---

## Phase 5 Verification Map

| Phase | REF | Test to run | Expected result |
|---|---|---|---|
| Phase 5 | `REF-011` | `cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml filtered_include_dep_resolves_version_without_seeding_transitive_items` | `1/1` test passes; filtered-path bug fixed without resolver regressions |
| Phase 5 | `REF-012` | `cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml latest_constraint_does_not_skip_sibling_semver_validation` | `1/1` test passes; mixed `Latest` + semver validation restored |
| Phase 5 | `REF-013` | `cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml equivalent_semver_syntax_accepts_same_resolved_version` | `1/1` test passes; equivalent semver syntax no longer conflicts |
| Phase 5 | `REF-014` | `cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml skill_resolution_prefers_dependency_closure_over_insertion_order` | `1/1` test passes; dependency-closure skill precedence restored |

---

## Bug Priority

| Bug | Severity | Frequency | Fix Complexity | Regression Test |
|---|---|---|---|---|
| #1 Filtered dep leak | High | Common | Medium | `filtered_include_dep_resolves_version_without_seeding_transitive_items` |
| #2 Latest bypass | High | Uncommon | Low | `latest_constraint_does_not_skip_sibling_semver_validation` |
| #3 Syntax comparison | Medium | Uncommon | Low-Medium | `equivalent_semver_syntax_accepts_same_resolved_version` |
| #4 Skill ordering | Medium | Common | Medium | `skill_resolution_prefers_dependency_closure_over_insertion_order` |

Recommended order: Bug #1 and its structural split first, then Bug #2, Bug #3, and Bug #4 once the resolver modules are isolated enough to patch cleanly.
