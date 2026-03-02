# Tech Debt

Code and test cleanup.

## High

### TD-1: Unify spawn execution lifecycle paths
- **Source**: code-cleanup #1
- **Priority**: high
- **Description**: Duplicated lifecycle logic between background and blocking spawn execution paths in `src/meridian/lib/ops/_spawn_execute.py` (`_execute_spawn_background`, `_execute_spawn_blocking`).
- **Direction**: Extract shared lifecycle helper(s) for start/session/materialize/cleanup and subrun event emission. Keep transport-specific behavior in thin wrappers.
- **Acceptance**: No behavior change in spawn state transitions, session tracking, or emitted subrun events.

### TD-2: Consolidate space-resolution helpers and `@name` reference loading
- **Source**: code-cleanup #2, known-issues #5
- **Description**: Duplicate space-id resolution logic across `src/meridian/lib/ops/_runtime.py` (`resolve_space_id`, `require_space_id`) and `src/meridian/lib/ops/_spawn_query.py` (`_resolve_space_id`). Related: `-f @name` reference loading reads `MERIDIAN_SPACE_ID` directly rather than using threaded/explicit operation space context (same root cause).
- **Direction**: One canonical resolver in runtime helpers, consumed from spawn query/ops layers. Fix `@name` loading to use threaded context.
- **Acceptance**: Space-required errors/messages remain consistent across CLI/MCP/ops paths.

## Medium

### TD-3: Merge repeated warning/normalization utilities
- **Source**: code-cleanup #3
- **Description**: Repeated utility patterns (`_merge_warnings`, space normalization, string stripping) in `src/meridian/lib/ops/spawn.py` and `src/meridian/lib/ops/_spawn_prepare.py`.
- **Direction**: Add shared internal utility module for warning composition and input normalization.

### TD-4: Consolidate CLI spawn plumbing tests
- **Source**: test-cleanup #1
- **Description**: Overlapping CLI plumbing tests across `test_cli_spawn_show_flags.py`, `test_cli_spawn_stats.py`, `test_cli_spawn_wait_multi.py`, `test_cli_spawn_stream_flags.py`.
- **Direction**: Create `tests/test_cli_spawn_plumbing.py` with parameterized payload/exit-code assertions.

### TD-5: Remove overlapping streaming test coverage
- **Source**: test-cleanup #2
- **Description**: Duplicate coverage between `test_streaming_s5_subspawn_enrichment.py` and `test_spawn_output_streaming.py`.
- **Direction**: Fold unique assertions into canonical file and remove duplicate cases.

### TD-6: Centralize subprocess test helpers
- **Source**: test-cleanup #3
- **Description**: Repeated helper boilerplate (`_spawn_cli`, `_write_skill`, `_write_config`) across multiple test modules.
- **Direction**: Add shared test helper module (`tests/helpers/cli.py`, `tests/helpers/fixtures.py`).
