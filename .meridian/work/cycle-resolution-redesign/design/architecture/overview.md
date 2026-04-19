# Resolver Architecture Overview

## Purpose

The resolver transforms a user's `mars.toml` configuration into a fully resolved dependency graph. It handles:
- Version constraint intersection and selection (MVS or maximize)
- Transitive dependency discovery through manifests
- Skill reference resolution from frontmatter
- Filter accumulation for downstream materialization
- Lock file integration for reproducible builds

## Current Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      resolve/mod.rs                         │
│                       (4,464 lines)                         │
├─────────────────────────────────────────────────────────────┤
│  Public API                                                 │
│  ├── resolve() → ResolvedGraph                              │
│  ├── ResolvedGraph, ResolvedNode, RootedSourceRef           │
│  ├── VersionConstraint, ResolveOptions                      │
│  └── parse_version_constraint()                             │
├─────────────────────────────────────────────────────────────┤
│  Resolution Engine                                          │
│  ├── resolve_package_bottom_up(11+ params)                  │
│  ├── resolve_single_source(), resolve_git_source()          │
│  ├── select_version() — MVS/maximize                        │
│  └── validate_all_constraints()                             │
├─────────────────────────────────────────────────────────────┤
│  Internal State                                             │
│  ├── registry: IndexMap<SourceName, RegisteredPackage>      │
│  ├── package_states, id_index                               │
│  ├── constraints (conflated with filters)                   │
│  ├── filter_constraints                                     │
│  ├── stack, visited, package_versions                       │
│  └── RegisteredPackage (3 parallel representations)         │
├─────────────────────────────────────────────────────────────┤
│  Support Functions                                          │
│  ├── resolve_skill_ref() — insertion order lookup           │
│  ├── apply_subpath(), is_item_excluded()                    │
│  └── manifest request collection                            │
├─────────────────────────────────────────────────────────────┤
│  Tests (~2,900 lines)                                       │
│  ├── tracker_tests — VisitedSet, PackageVersions            │
│  └── tests — full integration                               │
└─────────────────────────────────────────────────────────────┘
         │
         └── compat.rs (127 lines) — constraint compatibility
```

## Target Architecture

```
resolve/
├── mod.rs                 # Public API, orchestration (~200 lines)
│   ├── pub fn resolve()
│   └── Re-exports
│
├── types.rs               # Public data types (~150 lines)
│   ├── ResolvedGraph
│   ├── ResolvedNode
│   ├── RootedSourceRef
│   ├── VersionConstraint
│   └── ResolveOptions
│
├── constraint.rs          # Version parsing (~50 lines)
│   └── parse_version_constraint()
│
├── compat.rs              # Constraint compatibility (existing, 127 lines)
│   └── VersionConstraint::compatible_with()
│
├── context.rs             # Resolver state encapsulation (~200 lines)
│   ├── ResolverContext (11 fields → 1 struct)
│   │   ├── version_constraints    ← split from 'constraints'
│   │   └── materialization_filters ← split from 'filter_constraints'
│   └── VisitedSet, PackageVersions
│
├── package.rs             # Package resolution (~300 lines)
│   ├── RegisteredPackage (simplified)
│   ├── resolve_package_bottom_up(&mut ctx)
│   └── manifest request collection
│
├── version.rs             # Version selection (~200 lines)
│   ├── resolve_single_source()
│   ├── resolve_git_source()
│   ├── select_version()
│   └── validate_all_constraints()
│
├── skill.rs               # Skill resolution (~150 lines)
│   ├── SkillResolver (closure-ordered)
│   └── resolve_skill_ref()
│
├── filter.rs              # Filter handling (~50 lines)
│   ├── is_item_excluded()
│   └── push_filter_constraint()
│
├── path.rs                # Path validation (~100 lines)
│   ├── apply_subpath()
│   └── source_id_for_pending_spec()
│
└── tests/                 # Test modules (~2,900 lines total)
    ├── mod.rs             # MockProvider, helpers
    ├── tracker_tests.rs
    ├── version_tests.rs
    ├── skill_tests.rs
    ├── filter_tests.rs
    └── integration_tests.rs
```

## Key Architectural Changes

### 1. State Encapsulation (ResolverContext)

Before:
```rust
fn resolve_package_bottom_up(
    pending_src: &PendingSource,
    seed_items: bool,
    provider: &dyn SourceProvider,
    locked: Option<&LockFile>,
    options: &ResolveOptions,
    diag: &mut DiagnosticCollector,
    registry: &mut IndexMap<...>,
    package_states: &mut HashMap<...>,
    id_index: &mut HashMap<...>,
    constraints: &mut HashMap<...>,
    filter_constraints: &mut HashMap<...>,
    stack: &mut Vec<...>,
) -> Result<(), MarsError>
```

After:
```rust
fn resolve_package_bottom_up(
    ctx: &mut ResolverContext,
    pending_src: &PendingSource,
    seed_items: bool,
    provider: &dyn SourceProvider,
    locked: Option<&LockFile>,
    options: &ResolveOptions,
    diag: &mut DiagnosticCollector,
) -> Result<(), MarsError>
```

### 2. Constraint/Filter Separation

Before: `constraints` and `filter_constraints` are both used during resolution, with unclear boundaries.

After:
- `version_constraints`: Used only for version selection and validation
- `materialization_filters`: Used only for output assembly and item exclusion

This separation fixes Bug #1 (filtered dep leak).

### 3. Skill Resolution Ordering

Before: Linear scan over `registry` in IndexMap insertion order (arbitrary).

After: `SkillResolver` computes dependency closure from `ResolvedNode.deps` and searches in topological order (dependencies before dependents).

This fixes Bug #4 (skill lookup uses insertion order).

## Data Flow

```
mars.toml (EffectiveConfig)
    │
    ▼
┌─────────────────────────────────────┐
│         resolve()                   │
│  ┌─────────────────────────────┐    │
│  │    ResolverContext          │    │
│  │    ├── version_constraints  │    │
│  │    ├── materialization_filters│   │
│  │    └── registry             │    │
│  └─────────────────────────────┘    │
│              │                      │
│              ▼                      │
│  resolve_package_bottom_up()        │
│  ├── resolve_git_source()           │
│  ├── select_version()               │
│  └── seed_items_for_request()       │
│              │                      │
│              ▼                      │
│  DFS traversal (skill refs)         │
│  └── SkillResolver::resolve()       │
│              │                      │
│              ▼                      │
│  validate_all_constraints()         │
│              │                      │
│              ▼                      │
│  ctx.into_graph()                   │
└─────────────────────────────────────┘
    │
    ▼
ResolvedGraph
├── nodes: IndexMap<SourceName, ResolvedNode>
├── order: Vec<SourceName>
├── id_index: HashMap<SourceId, SourceName>
└── filters: HashMap<SourceName, Vec<FilterMode>>
```

## Bug Fix Integration

| Bug | Root Cause | Fix Location | Prerequisite |
|-----|------------|--------------|--------------|
| #1 Filtered dep leak | Resolution/materialization conflation | `context.rs` split + `package.rs` usage | REF-005 |
| #2 Latest bypasses validation | `has_latest` short-circuit | `version.rs` validate_all_constraints | REF-007 |
| #3 Syntax comparison | Comparing constraint strings | `version.rs` select_version | REF-007 |
| #4 Skill insertion order | IndexMap iteration order | `skill.rs` SkillResolver | REF-008 |

All bug fixes depend on the structural refactoring being complete (REF-001 through REF-010), which creates clean module boundaries and makes the fixes reviewable.
