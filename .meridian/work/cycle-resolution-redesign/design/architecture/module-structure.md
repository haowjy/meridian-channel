# Resolver Module Structure

## Current State

```
resolve/
├── mod.rs      # 4,464 lines: everything
└── compat.rs   # 127 lines: version constraint compatibility
```

The god module owns:
- Graph data types (ResolvedGraph, ResolvedNode, RootedSourceRef)
- Version constraint types and parsing (VersionConstraint, parse_version_constraint)
- Traversal state (VisitedSet, PackageVersions, PackageResolutionState)
- Package resolution (resolve_package_bottom_up, resolve_single_source, resolve_git_source)
- Version selection (select_version)
- Manifest loading (collect_manifest_requests, collect_git/path_manifest_requests)
- Path/subpath validation (apply_subpath)
- Filter handling (is_item_excluded, is_unfiltered_request, push_filter_constraint)
- Skill resolution (resolve_skill_ref, parse_pending_item_skill_deps)
- ~2,900 lines of tests

## Proposed Structure

```
resolve/
├── mod.rs              # Public API: resolve(), ResolvedGraph, ResolveOptions
├── types.rs            # Public types: ResolvedNode, RootedSourceRef, VersionConstraint
├── constraint.rs       # Version parsing and intersection
├── compat.rs           # Constraint compatibility (existing)
├── context.rs          # ResolverContext: encapsulated mutable state
├── package.rs          # Package resolution: resolve_package_bottom_up
├── version.rs          # Version selection: select_version, resolve_git_source
├── skill.rs            # Skill lookup: resolve_skill_ref with closure ordering
├── filter.rs           # Filter accumulation: separate from version constraints
├── path.rs             # Subpath validation: apply_subpath
└── tests/              # Test directory
    ├── mod.rs
    ├── version_tests.rs
    ├── skill_tests.rs
    ├── filter_tests.rs
    └── integration_tests.rs
```

## Module Responsibilities

### mod.rs (Public API)
- `pub fn resolve()` — orchestrates resolution phases
- Re-exports public types from types.rs
- Owns the high-level algorithm coordination

### types.rs (Public Data Types)
- `ResolvedGraph` — output graph structure
- `ResolvedNode` — single node in graph
- `RootedSourceRef` — checkout provenance
- `PendingItem` — item in DFS queue (may stay internal)

### constraint.rs (Version Parsing)
- `VersionConstraint` enum — Semver/Latest/RefPin
- `parse_version_constraint()` — string to constraint
- Constraint intersection logic

### context.rs (Resolver State)
Encapsulates the 11+ mutable parameters currently threaded through `resolve_package_bottom_up`:

```rust
pub struct ResolverContext {
    /// Package name → resolved package data
    registry: IndexMap<SourceName, RegisteredPackage>,
    /// Package name → resolution state (Resolved/Resolving)
    package_states: HashMap<SourceName, PackageResolutionState>,
    /// Source identity → source name (duplicate detection)
    id_index: HashMap<SourceId, SourceName>,
    /// Package name → version constraints (resolution)
    version_constraints: HashMap<SourceName, Vec<(String, VersionConstraint)>>,
    /// Package name → materialization filters (separate!)
    materialization_filters: HashMap<SourceName, Vec<FilterMode>>,
    /// DFS traversal queue
    stack: Vec<PendingItem>,
    /// Visited items with version tracking
    visited: VisitedSet,
    /// Package version conflict detection
    package_versions: PackageVersions,
}
```

Key change: **split `constraints` into `version_constraints` and `materialization_filters`** to fix the filtered dep leak bug.

### package.rs (Package Resolution)
- `RegisteredPackage` — internal package state
- `resolve_package_bottom_up()` — recursive resolution
- Manifest request collection
- Package identity validation

### version.rs (Version Selection)
- `resolve_single_source()` — dispatch git vs path
- `resolve_git_source()` — git version resolution
- `select_version()` — MVS/maximize selection
- `validate_all_constraints()` — post-resolution validation (fixed for Latest)

### skill.rs (Skill Resolution)
- `resolve_skill_ref()` — skill lookup with **dependency closure ordering**
- `parse_pending_item_skill_deps()` — frontmatter parsing delegation

Key change: **search order uses dependency closure, not insertion order**.

### filter.rs (Filter Handling)
- `is_item_excluded()` — check exclusion
- `push_filter_constraint()` — accumulate filters
- `is_unfiltered_request()` — check All mode

### path.rs (Path Validation)
- `apply_subpath()` — subpath validation and canonicalization
- `source_id_for_pending_spec()` — source identity computation

## Data Structure Changes

### ResolverContext (New)
Replaces the 11+ mutable parameters. Methods instead of function arguments:

```rust
impl ResolverContext {
    pub fn new() -> Self;
    
    // Package operations
    pub fn register_package(&mut self, ...);
    pub fn get_package(&self, name: &SourceName) -> Option<&RegisteredPackage>;
    
    // Constraint tracking (split!)
    pub fn add_version_constraint(&mut self, package: &SourceName, requester: &str, constraint: VersionConstraint);
    pub fn add_materialization_filter(&mut self, package: &SourceName, filter: &FilterMode);
    
    // State queries
    pub fn package_state(&self, name: &SourceName) -> Option<&PackageResolutionState>;
    pub fn set_package_state(&mut self, name: SourceName, state: PackageResolutionState);
    
    // Traversal
    pub fn push_pending(&mut self, item: PendingItem);
    pub fn pop_pending(&mut self) -> Option<PendingItem>;
    
    // Output assembly
    pub fn into_graph(self) -> ResolvedGraph;
}
```

### RegisteredPackage (Simplified)
Remove redundant parallel representations:

```rust
// Before: 3 parallel representations
struct RegisteredPackage {
    discovered: Vec<DiscoveredItem>,
    discovered_index: HashMap<(ItemKind, ItemName), DiscoveredItem>,
    skill_names: HashSet<ItemName>,
    // ...
}

// After: single indexed representation
struct RegisteredPackage {
    node: ResolvedNode,
    /// Indexed discovered items
    items: IndexMap<(ItemKind, ItemName), DiscoveredItem>,
    constraint: VersionConstraint,
    spec: SourceSpec,
    is_local: bool,
}

impl RegisteredPackage {
    fn item(&self, kind: ItemKind, name: &ItemName) -> Option<&DiscoveredItem> {
        self.items.get(&(kind, name.clone()))
    }
    
    fn has_skill(&self, skill: &ItemName) -> bool {
        self.items.contains_key(&(ItemKind::Skill, skill.clone()))
    }
    
    fn skill_names(&self) -> impl Iterator<Item = &ItemName> {
        self.items.iter()
            .filter(|((kind, _), _)| *kind == ItemKind::Skill)
            .map(|((_, name), _)| name)
    }
}
```

### SkillResolver (New Helper)
Encapsulates skill lookup with proper ordering:

```rust
/// Resolves skill references with dependency closure ordering.
struct SkillResolver<'a> {
    registry: &'a IndexMap<SourceName, RegisteredPackage>,
    dep_order: Vec<SourceName>, // computed from registry.deps
}

impl<'a> SkillResolver<'a> {
    fn new(registry: &'a IndexMap<SourceName, RegisteredPackage>) -> Self;
    
    /// Resolve skill, searching containing package first, then deps in closure order.
    fn resolve(&self, skill: &ItemName, requester_package: &SourceName) 
        -> Result<ResolvedSkill, ResolutionError>;
}
```
