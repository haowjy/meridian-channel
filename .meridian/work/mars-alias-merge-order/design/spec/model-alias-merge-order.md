# Model Alias Merge Order — Behavioral Specification

## Context

Model aliases from the dependency tree are merged during `resolve_graph` (phase 2 of sync). The merge uses `merge_model_config()` which applies a first-in-slice-wins policy. The problem is that the input slice ordering comes from topological sort, which breaks ties alphabetically for siblings — not by the consumer's declaration order in `mars.toml`.

## Precedence (unchanged)

- **Layer 2 (highest)**: Consumer `[models]` — always wins
- **Layer 1**: Dependencies — override builtins, declaration-order first-wins among siblings
- **Layer 0 (lowest)**: Builtins

## EARS Statements

### S-ORDER-1: Declaration-order sibling tiebreak
**When** two sibling dependencies (no dependency relationship between them) both define the same model alias, **the system shall** resolve the conflict using the consumer's `mars.toml [dependencies]` declaration order, where the dep listed first wins.

### S-ORDER-2: Transitive dep ordering within a subtree
**When** a dependency B has its own transitive deps D and E that define the same alias, **the system shall** use B's manifest declaration order to determine D-vs-E precedence within B's subtree.

### S-ORDER-4: Diamond dependency sponsor resolution
**When** a transitive dependency D is reachable from multiple direct dependencies (e.g., both A and B depend on D), **the system shall** assign D the declaration position of the earliest (lowest-index) direct dep that reaches it, so D's model aliases are processed as part of the earliest sponsor's subtree.

### S-ORDER-3: Dependency-before-dependent ordering preserved
**When** a dependency D is a transitive dep of B, and both define the same alias, **the system shall** let B's definition override D's (dependent wins over its own deps), consistent with current topological ordering behavior.

### S-WARN-1: Conflict warning with both dep names
**When** a model alias conflict is resolved by declaration-order tiebreak between siblings, **the system shall** emit a diagnostic warning naming both the winning and losing dependencies and suggesting an explicit `[models.X]` override.

### S-WARN-2: Consumer override suppresses warning
**When** the consumer's `[models]` section defines an alias that would otherwise conflict between deps, **the system shall not** emit a conflict warning for that alias (consumer override is intentional, not a tiebreak).

### S-DETERM-1: Deterministic output
**When** the same `mars.toml` and dependency tree are resolved, **the system shall** produce identical merged aliases every time. Declaration order is the determinism source for sibling ties.

### S-COMPAT-1: Non-blocking sync
**When** model alias conflicts occur during sync, **the system shall** warn and continue — conflicts do not block the sync pipeline.

### S-WARN-3: Three-or-more-way conflict warnings
**When** three or more deps define the same alias, **the system shall** emit one warning per losing dep, each naming the winning dep, so the user sees exactly which deps are conflicting.

### S-COMPAT-2: Unchanged output format
**When** `models-merged.json` is written in `finalize`, **the system shall** use the same JSON format as before. Only the content ordering changes.

### S-FINALIZE-1: Finalize uses same ordering as resolve_graph
**When** `finalize` builds `dep_models` for `models-merged.json` persistence, **the system shall** use the same declaration-order-aware ordering as `resolve_graph` for the dependency slice ordering. Note: `finalize` passes empty consumer config (deps-only persistence), so the merged *content* differs from `resolve_graph`'s full merge — but the dependency *ordering* must be identical.
