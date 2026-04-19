# Refactor Agenda

This document sequences structural rearrangement work. Order matters. Earlier items reduce surface area and create stable seams for later behavior changes.

All verification commands below are written to run from the `meridian-cli` repo root and target the adjacent `mars-agents` checkout explicitly:

```bash
cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml ...
```

## Verification Baseline

- Current full library baseline: `cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml --lib` -> `563/563` library tests pass.
- Current resolver baseline: `cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml resolve::` -> `81/81` resolver tests pass.
- Phase 5 intentionally adds four new resolver regression tests. After REF-014 lands, the new expected baselines are `567/567` library tests and `85/85` resolver tests.

## Phase 1: Test Extraction (No Behavior Change)

**REF-001: Extract tests to dedicated resolver test files**

Move resolver tests out of `src/resolve/mod.rs` into dedicated files:
- `src/resolve/tests/mod.rs` — test wiring and shared helpers
- `src/resolve/tests/tracker_tests.rs` — `VisitedSet`, `PackageVersions`, and policy tests
- `src/resolve/tests/version_tests.rs` — version parsing and selection tests
- `src/resolve/tests/skill_tests.rs` — skill resolution tests
- `src/resolve/tests/filter_tests.rs` — filter collection and seeding tests
- `src/resolve/tests/integration_tests.rs` — end-to-end `resolve()` integration tests

**Why first:** This is pure code movement. It shrinks `src/resolve/mod.rs` before semantic refactors start.

**Exit criteria**
- Resolver test bodies live in dedicated `src/resolve/tests/*.rs` files instead of a monolithic inline test block.
- `src/resolve/mod.rs` only declares the test modules and shared test helpers still required at the module boundary.
- Resolver behavior is unchanged after the move.

**Verification command**
```bash
cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml resolve::
```

**Expected result**
- `81/81` resolver tests pass.
- No resolver behavior regressions.

### Phase 1 Exit Criteria

**Exit criteria**
- REF-001 is complete and committed separately from later refactors.
- The resolver-specific suite still passes after the extraction.
- The full library suite stays at the pre-refactor baseline.

**Verification command**
```bash
cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml --lib
```

**Expected result**
- `563/563` library tests pass.
- No regressions outside `resolve`.

---

## Phase 2: Type Extraction (No Behavior Change)

**REF-002: Extract `types.rs`**

Move public types out of `src/resolve/mod.rs`:
- `ResolvedGraph`
- `ResolvedNode`
- `RootedSourceRef`
- `VersionConstraint` + `Display`
- `ResolveOptions`
- `PendingItem`
- `VersionCheckResult`
- `ResolvedVersion`

Re-export from `src/resolve/mod.rs` so downstream call sites keep the same public API.

**Exit criteria**
- Public resolver data types live in `src/resolve/types.rs`.
- `src/resolve/mod.rs` re-exports the moved types, and downstream modules compile without call-site churn unrelated to the extraction.
- The public resolver API observed by other modules remains unchanged.

**Verification command**
```bash
cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml --lib
```

**Expected result**
- `563/563` library tests pass.
- No public API regressions in modules that consume `crate::resolve::*`.

**REF-003: Extract `constraint.rs`**

Move version parsing logic:
- `parse_version_constraint()`
- Associated helper logic

**Exit criteria**
- Version constraint parsing helpers live in `src/resolve/constraint.rs`.
- `parse_version_constraint()` remains reachable through `crate::resolve::parse_version_constraint`.
- Parsing behavior is unchanged for `latest`, exact tags, semver ranges, and ref pins.

**Verification command**
```bash
cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml resolve::tests::parse_
```

**Expected result**
- `11/11` parse-focused resolver tests pass.
- No regressions in constraint parsing semantics.

### Phase 2 Exit Criteria

**Exit criteria**
- REF-002 and REF-003 are complete with no behavior changes.
- The extracted files form stable import boundaries for later context and module extraction.
- The full library baseline remains unchanged.

**Verification command**
```bash
cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml --lib
```

**Expected result**
- `563/563` library tests pass.
- No regressions in resolver API or parsing behavior.

---

## Phase 3: ResolverContext Introduction (Structural Change)

**REF-004: Introduce `ResolverContext`**

Create `src/resolve/context.rs` with `ResolverContext` that encapsulates:
- `registry`
- `package_states`
- `id_index`
- `version_constraints`
- `materialization_filters`
- `stack`
- `visited`
- `package_versions`

Start as a thin wrapper: same data, fewer free-floating parameters.

**Exit criteria**
- Resolver state is grouped in `ResolverContext` rather than threaded through wide function signatures.
- The first cut preserves existing control flow and error behavior.
- Item/package version tracking still behaves identically after the move.

**Verification command**
```bash
cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml resolve::tracker_tests::
```

**Expected result**
- `13/13` tracker and version-policy tests pass.
- No regressions in visited-set or package-version bookkeeping.

**REF-005: Split constraint tracking**

Inside `ResolverContext`, separate:
- `version_constraints: HashMap<SourceName, Vec<(String, VersionConstraint)>>` — resolution decisions
- `materialization_filters: HashMap<SourceName, Vec<FilterMode>>` — item selection only

This is the structural prerequisite for [Bug #1](spec/bug-specifications.md#bug-1-filtered-dependency-leak).

**Exit criteria**
- Resolution decisions read from `version_constraints` only.
- Materialization decisions read from `materialization_filters` only.
- Existing filter accumulation behavior remains intact before the actual bug fix lands.

**Verification command**
```bash
cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml direct_and_transitive_filters_are_both_collected_for_same_source
```

**Expected result**
- `1/1` targeted filter-accumulation test passes.
- No regression in how direct and transitive filters are recorded.

### Phase 3 Exit Criteria

**Exit criteria**
- `ResolverContext` exists and all resolver internals consume it consistently.
- Constraint tracking and materialization filters are represented separately.
- Structural changes still preserve pre-bug-fix behavior.

**Verification command**
```bash
cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml --lib
```

**Expected result**
- `563/563` library tests pass.
- No regressions while preparing for behavior fixes.

---

## Phase 4: Module Extraction (No Behavior Change)

**REF-006: Extract `package.rs`**

Move package resolution functions:
- `RegisteredPackage`
- `resolve_package_bottom_up()`
- `seed_items_for_request()`
- `collect_manifest_requests()` and helpers
- `PackageResolutionState`

**Exit criteria**
- Package traversal and manifest request logic live in `src/resolve/package.rs`.
- Resolver control flow still passes through the same package-resolution checkpoints.
- No behavior change in transitive dependency traversal.

**Verification command**
```bash
cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml source_with_transitive_dep
```

**Expected result**
- `1/1` targeted package-traversal test passes.
- No regression in transitive package resolution.

**REF-007: Extract `version.rs`**

Move version selection logic:
- `resolve_single_source()`
- `resolve_git_source()`
- `select_version()`
- `validate_all_constraints()`

**Exit criteria**
- Version selection and post-resolution validation live in `src/resolve/version.rs`.
- Locked-version, maximize, and MVS behavior are unchanged before Phase 5 bug fixes.
- The new module boundary is clean enough to patch validation logic without reopening unrelated code.

**Verification command**
```bash
cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml resolve::tests::maximize_
```

**Expected result**
- `3/3` maximize-mode tests pass.
- No regression in targeted version-selection behavior.

**REF-008: Extract `skill.rs`**

Move skill resolution logic:
- `resolve_skill_ref()`
- `parse_pending_item_skill_deps()`
- `discovered_item_markdown_path()`
- `primary_package_constraint()`

**Exit criteria**
- Skill resolution logic lives in `src/resolve/skill.rs`.
- Same-package lookup and error reporting remain unchanged before the closure-order bug fix.
- Resolver still surfaces enough search context for future bug-fix assertions.

**Verification command**
```bash
cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml skill_not_found_has_requester_and_search_context
```

**Expected result**
- `1/1` skill-resolution context test passes.
- No regression in baseline skill lookup diagnostics.

**REF-009: Extract `filter.rs`**

Move filter handling logic:
- `is_item_excluded()`
- `push_filter_constraint()`
- `is_unfiltered_request()`

**Exit criteria**
- Filter-specific helpers live in `src/resolve/filter.rs`.
- Filter accumulation and filter-driven seeding behavior are unchanged before REF-011.
- Extraction leaves a narrow seam for the later filtered-dependency bug fix.

**Verification command**
```bash
cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml filtered_parent_dep_does_not_seed_unfiltered_child_items
```

**Expected result**
- `1/1` focused filter-seeding regression test passes.
- No regression in current filtered traversal behavior.

**REF-010: Extract `path.rs`**

Move path validation logic:
- `apply_subpath()`
- `source_id_for_pending_spec()`

**Exit criteria**
- Path and subpath validation live in `src/resolve/path.rs`.
- Source identity and path traversal protections remain unchanged.
- Cross-checkout/package-root semantics remain intact.

**Verification command**
```bash
cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml resolve::tests::apply_subpath_
```

**Expected result**
- `5/5` subpath/path validation tests pass.
- No regression in subpath safety checks.

### Phase 4 Exit Criteria

**Exit criteria**
- REF-006 through REF-010 are complete and each extracted concern lives in its own module.
- `src/resolve/mod.rs` is orchestration glue plus exports, not a 4k-line implementation dump.
- The resolver remains behaviorally identical to the pre-bug-fix baseline.

**Verification command**
```bash
cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml --lib
```

**Expected result**
- `563/563` library tests pass.
- No regressions before entering behavior-changing work.

---

## Phase 5: Bug Fixes (Behavior Change)

With clean module boundaries in place, fix the known resolver bugs. The detailed regression scenarios live in [spec/bug-specifications.md](spec/bug-specifications.md).

**REF-011: Fix filtered dependency leak (Bug #1)**

In `resolve_package_bottom_up()`:
- Use `version_constraints` for resolution decisions.
- Use `materialization_filters` only for output assembly.
- Ensure filtered dependencies still resolve to concrete versions, but do not eagerly seed items that filters exclude.

**New test name**
- `filtered_include_dep_resolves_version_without_seeding_transitive_items`

**Test scenario**
- Setup: a direct dependency `parent` is filtered to include only `runner`; `parent` depends on `child` with no filter, and `child` exports items that would be traversed if seeded.
- Action: run resolver on the consumer config with the filtered `parent` dependency.
- Expected result: `parent` and `child` both appear in the resolved graph for version-selection purposes, but `child` items are not eagerly seeded or traversed through the filtered path.

**EARS ID**
- `REQ-FIL-001`, `REQ-FIL-002` in [spec/resolver-behavioral-contract.md](spec/resolver-behavioral-contract.md)

**Exit criteria**
- Filtered dependencies still contribute version selection information.
- Transitive packages reached through a filtered parent are resolved, but excluded items are not eagerly seeded.
- New regression coverage exists for the filtered-parent/unfiltered-child case.

**Verification command**
```bash
cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml filtered_include_dep_resolves_version_without_seeding_transitive_items
```

**Expected result**
- `1/1` new REF-011 regression test passes.
- Resolver baseline increases to `82/82` tests when `cargo test ... resolve::` is rerun.

**REF-012: Fix Latest validation bypass (Bug #2)**

In `validate_all_constraints()`:
- Remove the `if has_latest { continue; }` short-circuit.
- Validate `Latest` packages against sibling semver constraints using the resolved version.
- Emit `VersionConflict` when the resolved version violates a non-Latest constraint.

**New test name**
- `latest_constraint_does_not_skip_sibling_semver_validation`

**Test scenario**
- Setup: two dependents reference the same package; one uses `Latest`, the other uses `^1.0`; available versions resolve `Latest` to `v2.0.0`.
- Action: run resolver and allow post-resolution validation to execute.
- Expected result: resolver emits `VersionConflict` because the resolved version selected by `Latest` does not satisfy the sibling semver constraint.

**EARS ID**
- `REQ-VAL-001`, `REQ-VAL-002` in [spec/resolver-behavioral-contract.md](spec/resolver-behavioral-contract.md)

**Exit criteria**
- `Latest` no longer suppresses semver validation for the same package.
- Mixed `Latest` + semver constraints fail when the resolved version violates the semver requirement.
- New regression coverage exists for the mixed-constraint failure path.

**Verification command**
```bash
cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml latest_constraint_does_not_skip_sibling_semver_validation
```

**Expected result**
- `1/1` new REF-012 regression test passes.
- Resolver baseline increases to `83/83` tests when `cargo test ... resolve::` is rerun.

**REF-013: Fix constraint syntax comparison (Bug #3)**

In version validation and compatibility checks:
- Compare resolved versions, not raw constraint syntax strings.
- Treat semver expressions as compatible when they both accept the resolved version.

**New test name**
- `equivalent_semver_syntax_accepts_same_resolved_version`

**Test scenario**
- Setup: two dependents request the same package using syntactically different but semantically equivalent semver expressions; available versions include at least one version both expressions accept.
- Action: run resolver through version selection and post-resolution validation.
- Expected result: resolver accepts the package, selects a shared resolved version, and does not raise a false constraint conflict.

**EARS ID**
- `REQ-VAL-001`, `REQ-VAL-003` in [spec/resolver-behavioral-contract.md](spec/resolver-behavioral-contract.md)

**Exit criteria**
- Constraint validation compares semantic acceptance of the resolved version rather than string equality.
- Equivalent constraint spellings do not raise false conflicts.
- New regression coverage exists for syntactically different but semantically equivalent constraints.

**Verification command**
```bash
cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml equivalent_semver_syntax_accepts_same_resolved_version
```

**Expected result**
- `1/1` new REF-013 regression test passes.
- Resolver baseline increases to `84/84` tests when `cargo test ... resolve::` is rerun.

**REF-014: Fix skill lookup order (Bug #4)**

In `resolve_skill_ref()`:
- Build the dependency closure from registry dependency edges.
- Search same package first, then dependency closure order, not `IndexMap` insertion order.
- Introduce a `SkillResolver` helper that precomputes closure order.

**New test name**
- `skill_resolution_prefers_dependency_closure_over_insertion_order`

**Test scenario**
- Setup: a requester package depends on `my-dep`, an unrelated sibling package is inserted earlier in the registry, and both export the same skill name.
- Action: resolve the requester agent's frontmatter skill reference.
- Expected result: resolver selects the skill from `my-dep`, not the unrelated earlier sibling.

**EARS ID**
- `REQ-SKL-001`, `REQ-SKL-002` in [spec/resolver-behavioral-contract.md](spec/resolver-behavioral-contract.md)

**Exit criteria**
- Same-package precedence still holds.
- Dependency-closure packages win over unrelated earlier-inserted siblings.
- New regression coverage exists for dependency-closure ordering.

**Verification command**
```bash
cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml skill_resolution_prefers_dependency_closure_over_insertion_order
```

**Expected result**
- `1/1` new REF-014 regression test passes.
- Resolver baseline increases to `85/85` tests when `cargo test ... resolve::` is rerun.

### Phase 5 Exit Criteria

**Exit criteria**
- REF-011 through REF-014 all land with their named regression tests in the same commits as the fixes.
- The resolver suite includes the four new regression tests and stays green end to end.
- No previously passing resolver or non-resolver library tests regress.

**Verification command**
```bash
cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml --lib
```

**Expected result**
- `567/567` library tests pass.
- `85/85` resolver tests pass when the suite is filtered with `cargo test ... resolve::`.
- No regressions outside the new bug-fix coverage.

---

## Phase 6: RegisteredPackage Simplification (Optional)

**REF-015: Consolidate `RegisteredPackage` representations**

Merge the parallel representations:
- Remove `discovered: Vec<DiscoveredItem>`
- Remove `skill_names: HashSet<ItemName>`
- Keep only `items: IndexMap<(ItemKind, ItemName), DiscoveredItem>`

Derive removed views by iterating `items`.

**Why last:** This is cleanup, not a prerequisite for correctness.

**Exit criteria**
- `RegisteredPackage` carries a single authoritative item representation.
- Removed views are derived rather than stored in parallel.
- The post-Phase-5 behavior and regression coverage remain intact.

**Verification command**
```bash
cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml resolve::
```

**Expected result**
- `85/85` resolver tests pass.
- No regression after the representation simplification.

### Phase 6 Exit Criteria

**Exit criteria**
- REF-015 is complete without changing user-visible resolver behavior.
- No Phase 5 bug-fix regression tests fail.
- The library suite remains at the post-Phase-5 baseline.

**Verification command**
```bash
cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml --lib
```

**Expected result**
- `567/567` library tests pass.
- No regressions after optional simplification.

---

## Phase Verification Summary

| Phase | Tests to run | Expected result |
|---|---|---|
| Phase 1: Test extraction | `cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml resolve::`<br/>`cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml --lib` | `81/81` resolver tests pass; `563/563` library tests pass; no regressions |
| Phase 2: Type extraction | `cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml resolve::tests::parse_`<br/>`cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml --lib` | `11/11` parse tests pass; `563/563` library tests pass; no regressions |
| Phase 3: ResolverContext | `cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml resolve::tracker_tests::`<br/>`cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml --lib` | `13/13` tracker tests pass; `563/563` library tests pass; no regressions |
| Phase 4: Module extraction | `cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml resolve::`<br/>`cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml --lib` | `81/81` resolver tests pass; `563/563` library tests pass; no regressions |
| Phase 5: Bug fixes | `cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml filtered_include_dep_resolves_version_without_seeding_transitive_items`<br/>`cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml latest_constraint_does_not_skip_sibling_semver_validation`<br/>`cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml equivalent_semver_syntax_accepts_same_resolved_version`<br/>`cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml skill_resolution_prefers_dependency_closure_over_insertion_order`<br/>`cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml resolve::`<br/>`cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml --lib` | Each new regression test passes `1/1`; resolver suite passes `85/85`; library suite passes `567/567`; no regressions |
| Phase 6: RegisteredPackage simplification | `cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml resolve::`<br/>`cargo test --manifest-path /home/jimyao/gitrepos/mars-agents/Cargo.toml --lib` | `85/85` resolver tests pass; `567/567` library tests pass; no regressions |
