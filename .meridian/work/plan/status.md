# Review Findings Fix - Status

## Phases

| # | Issue | Status | Notes |
|---|-------|--------|-------|
| 1 | Minor 5: Crash-safe writes not centralized | done | Replaced duplicates in ops/config.py and catalog/models.py with shared atomic_write_text |
| 2 | Minor 4: Two state persistence models | done | Documented rationale in work_store.py docstring |
| 3 | Major 2: Config schema diverged (primary.*) | done | Added 8 primary.* keys to _CONFIG_KEY_SPECS and _SECTION_ORDER |
| 4 | Major 3: Command registration simplification | done | Auto-generated handlers for simple commands, 4-file → 2-file for no-arg commands |
| 5 | Major 1: Launch/ops layering inversion | done | Moved ensure_explicit_work_item from process.py to launch_primary |
