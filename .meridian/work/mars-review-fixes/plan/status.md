# Implementation Status

## Phases

| Phase | Finding(s) | Status | Risk |
|-------|-----------|--------|------|
| 1. Canonicalize fix + help text | F4, F5, F6 | planned | low |
| 2. Atomic install dir | F13 | planned | medium |
| 3. Sync crash tolerance | F12 | planned | medium |
| 4a. Symlink containment (root) | F1 | planned | medium |
| 4b. Symlink-aware scanning | F3 | planned | low |
| 5. Git cache locking | F14 | planned | low |

## Execution Order

```
Round 1: Phase 1, Phase 2, Phase 3, Phase 4a, Phase 5  (all independent)
Round 2: Phase 4b                                       (after 4a — both touch mod.rs)
```

Phases 1, 2, 3, 4a, and 5 are fully independent and can execute in parallel.
Phase 4b should follow Phase 4a to avoid merge conflicts in mod.rs.

## Review Findings Incorporated

- **p715 (gpt-5.4, correctness):** Sync reorder rejected — `mars sync` can't replay mutations. Replaced with unmanaged-collision tolerance. atomic_install_dir docs corrected to not overclaim gap elimination.
- **p716 (opus, design quality):** Phase 4 split into 4a/4b. Check vs doctor symlink policies differentiated. Symlinks in link target dir are informational not blocking. Shared is_symlink helper added. cwd canonicalized before walk-up.

## Tier 3 Backlog (not planned for implementation)

- F15: Collision rename cross-package deps
- F16: DepSpec.items unused in resolver
- F17: Error model too coarse (string parsing in repair)
- F18: WELL_KNOWN/TOOL_DIRS layering
- F19: Shared frontmatter scanning (check/doctor)
- F20: link.rs decomposition
- F21: dispatch_result boilerplate
