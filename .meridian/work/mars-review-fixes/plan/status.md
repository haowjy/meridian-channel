# Implementation Status

## Phases

| Phase | Finding(s) | Status | Risk |
|-------|-----------|--------|------|
| 1. Canonicalize fix + help text | F4, F5, F6 | planned | low |
| 2. Atomic install dir | F13 | planned | medium |
| 3. Sync pipeline reorder | F12 | planned | medium |
| 4. Symlink containment | F1, F3 | planned | medium |
| 5. Git cache locking | F14 | planned | low |

## Execution Order

```
Round 1: Phase 1, Phase 2, Phase 3, Phase 5  (all independent)
Round 2: Phase 4                              (depends on Phase 1 — both touch doctor.rs)
```

Phases 1, 2, 3, and 5 are fully independent and can execute in parallel.
Phase 4 should follow Phase 1 to avoid merge conflicts in doctor.rs.

## Tier 3 Backlog (not planned for implementation)

- F15: Collision rename cross-package deps
- F16: DepSpec.items unused in resolver
- F17: Error model too coarse (string parsing in repair)
- F18: WELL_KNOWN/TOOL_DIRS layering
- F19: Shared frontmatter scanning (check/doctor)
- F20: link.rs decomposition
- F21: dispatch_result boilerplate
