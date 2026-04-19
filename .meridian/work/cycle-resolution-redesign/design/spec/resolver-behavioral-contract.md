# Resolver Behavioral Contract

This document specifies the behavioral contract the resolver must satisfy. These are the testable statements implementation verifies against.

## Resolution Semantics

### REQ-RES-001: Version Selection — MVS Default
When the resolver receives version constraints without explicit maximize mode, the resolver SHALL select the minimum version satisfying all constraints (Minimum Version Selection).

### REQ-RES-002: Version Selection — Maximize Mode
When the resolver receives `maximize: true` option, the resolver SHALL select the maximum version satisfying all constraints for targeted sources.

### REQ-RES-003: Version Selection — Locked Preference
When a locked version exists AND satisfies all constraints AND maximize mode is not active, the resolver SHALL prefer the locked version over computing a fresh selection.

### REQ-RES-004: Constraint Intersection
When multiple constraints apply to the same source, the resolver SHALL compute the intersection of all constraints and select a version that satisfies all of them.

### REQ-RES-005: Constraint Conflict Detection
When no version exists that satisfies all constraints for a source, the resolver SHALL emit a VersionConflict error with diagnostic information about which constraints are incompatible.

## Resolution Constraints vs Materialization Filters

### REQ-FIL-001: Filter Application Separation
Resolution constraints (which packages to resolve and at what version) SHALL be evaluated independently from materialization filters (which items to include in output).

### REQ-FIL-002: Filtered Dependency Resolution
When a dependency has an Include filter, the resolver SHALL still resolve the package and all its transitive dependencies, but MAY defer item seeding until the package is fully resolved.

### REQ-FIL-003: Filter Accumulation
When the same package is referenced from multiple locations with different filters, the resolver SHALL accumulate all filters and the sync phase SHALL compute the union of included items.

### REQ-FIL-004: Excluded Item Non-Traversal
When an item is excluded by a filter, the resolver SHALL NOT traverse its frontmatter skill dependencies.

## Package Identity

### REQ-PKG-001: Source Identity Uniqueness
When two different source names resolve to the same source identity (URL + subpath), the resolver SHALL emit DuplicateSourceIdentity error.

### REQ-PKG-002: Source Identity Consistency
When the same source name is referenced with different source identities, the resolver SHALL emit SourceIdentityMismatch error.

### REQ-PKG-003: Single Version Per Package
When a package is resolved, only one concrete version SHALL exist in the graph (no diamond with different versions).

## Skill Resolution

### REQ-SKL-001: Same-Package Precedence
When resolving a skill reference from frontmatter, the resolver SHALL first check the containing package before searching other packages.

### REQ-SKL-002: Dependency Closure Search
When a skill is not found in the containing package, the resolver SHALL search packages in dependency closure order (dependencies before dependents), not insertion order.

### REQ-SKL-003: Skill Not Found Error
When a skill reference cannot be resolved in any available package, the resolver SHALL emit SkillNotFound error listing searched packages.

## Version Validation

### REQ-VAL-001: Post-Resolution Validation
After resolution completes, the resolver SHALL validate that all semver constraints are satisfied by the resolved versions.

### REQ-VAL-002: Latest Constraint Validation
When a constraint is Latest, the resolver SHALL still validate that the resolved version is semver-compatible if other semver constraints exist for the same package.

### REQ-VAL-003: Syntax vs Resolved Comparison
Constraint compatibility checks SHALL compare against resolved versions, not constraint syntax strings.

## Graph Output

### REQ-OUT-001: Deterministic Order
The resolver SHALL produce deterministic alphabetical ordering in the output graph.

### REQ-OUT-002: Dependency Completeness
Every package in the output graph SHALL have all its dependencies also present in the graph.

### REQ-OUT-003: Filter Output
The output graph SHALL include accumulated filter constraints for each source, enabling downstream phases to compute materialized items.
