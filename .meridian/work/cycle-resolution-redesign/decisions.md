# Design Decisions

## DEC-001: Test Extraction First
**Decision:** Extract tests to `resolve/tests/` before any structural refactoring.

**Rationale:** 
- Tests are ~2,900 lines (65% of the file)
- Extracting them first makes subsequent changes reviewable
- Pure file movement — no behavior change, trivial to verify

**Alternatives rejected:**
- Interleave test extraction with refactoring — creates larger, harder-to-review commits
- Leave tests in place — makes subsequent refactoring diffs unreadable

## DEC-002: ResolverContext Over Incremental Parameter Reduction
**Decision:** Introduce a single `ResolverContext` struct to hold all mutable resolver state, rather than incrementally reducing parameters.

**Rationale:**
- 11+ mutable parameters indicate missing abstraction
- Single context struct enables future method-based API
- Creates clear ownership boundary for state
- Enables the constraint/filter split (REF-005) cleanly

**Alternatives rejected:**
- Incremental parameter reduction — still ends up at a context struct, with more intermediate states
- Multiple smaller contexts (PackageRegistry, ConstraintTracker, etc.) — over-engineering for current needs

## DEC-003: Explicit Constraint/Filter Naming
**Decision:** Rename `constraints` to `version_constraints` and `filter_constraints` to `materialization_filters`.

**Rationale:**
- Current names are ambiguous — "constraints" sounds like it constrains, but filters are for output selection
- Explicit names document the different purposes
- Makes the bug (mixing resolution with materialization) obvious in code review

**Alternatives rejected:**
- Keep current names — perpetuates confusion
- Just add comments — comments drift, names are checked

## DEC-004: Dependency Closure Ordering for Skill Lookup
**Decision:** Change skill lookup to search packages in dependency closure order (dependencies before dependents), not insertion order.

**Rationale:**
- Insertion order is an implementation artifact (IndexMap iteration)
- Dependency closure order is semantically meaningful: "use the skill from my dependency, not a sibling"
- Prevents shadowing surprises when package declaration order changes

**Alternatives rejected:**
- Explicit skill source annotation (`use skill from dep`) — bigger API change, deferred
- Alphabetical order — arbitrary, no semantic meaning

## DEC-005: Bug Fixes After Structural Refactor
**Decision:** Complete structural refactoring (REF-001 through REF-010) before attempting bug fixes (REF-011 through REF-014).

**Rationale:**
- Clean structure makes bug fixes easier to implement correctly
- Bug fixes in a 4,464-line god module are hard to review
- Structural changes don't require behavior verification; bug fixes do
- Keeps "no behavior change" commits separate from "intentional behavior change" commits

**Alternatives rejected:**
- Fix bugs first — harder to implement and review in current structure
- Mix bug fixes with refactoring — creates commits that are both structural and behavioral, impossible to verify

## DEC-006: Defer RegisteredPackage Simplification
**Decision:** RegisteredPackage simplification (REF-015) is optional and sequenced last.

**Rationale:**
- The three parallel representations (discovered, discovered_index, skill_names) are redundant but not incorrect
- Simplification is nice-to-have, not blocking
- Bug fixes are higher priority

**Alternatives rejected:**
- Require simplification for correctness — over-scoped
- Skip simplification entirely — leaves known technical debt

## DEC-007: Module Boundaries Follow Responsibility
**Decision:** New modules (package.rs, version.rs, skill.rs, filter.rs, path.rs) are named for their responsibility, not their primary type.

**Rationale:**
- `version.rs` contains version selection, not just the Version type
- `skill.rs` contains skill resolution, not just skill types
- Responsibility-based naming scales better as modules grow

**Alternatives rejected:**
- Type-based naming (e.g., `registered_package.rs`) — conflates data definition with behavior
- Feature-based naming (e.g., `mvs.rs`) — too narrow, requires renaming when scope expands
