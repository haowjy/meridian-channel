# Bugs

Runtime bugs and correctness issues.

## High

### BUG-1: Orphaned spawns stay "running" forever after process kill
- **Source**: known-issues #1, migration-notes p4/p5 weirdness
- **Description**: When a `meridian spawn` parent is killed or crashes, the child can orphan and the run record remains `status: "running"` indefinitely. Space lock cleanup exists (`cleanup_orphaned_locks()`), but spawn/run cleanup parity is missing.
- **Direction**: Add child PID tracking and `cleanup_orphaned_runs()` or equivalent finalization on termination signals.

### BUG-2: `report.md` not overwritten cleanly between runs
- **Source**: known-issues #4
- **Description**: Report behavior can persist stale output between runs, and lookup can resolve wrong report when run IDs repeat across spaces.
- **Related plan**: `plans/space-plumbing-fix.md` Step 1

## Medium

### BUG-3: Token usage always reports 0/0
- **Source**: migration-notes lines 13, 17
- **Description**: Manual spawn smoke runs reported `input_tokens=0` and `output_tokens=0` despite successful execution. Persists even after switching prompt transport to stdin. Indicates usage propagation gap in harness adapters.

### BUG-4: Thin auto-extracted reports with pseudo-paths in `files_touched`
- **Source**: migration-notes r1 weirdness
- **Description**: Spawn report extraction produces thin reports that don't reflect substantive actions. `files_touched` includes non-file pseudo-paths (`scope/terminology`, `scope/problem/target`).
- **Direction**: Investigate extraction pipeline (`src/meridian/lib/extract/report.py`, `src/meridian/lib/extract/files_touched.py`) and streaming event normalization.

### BUG-5: Empty artifacts on spawn failure (timeout/crash)
- **Source**: migration-notes p5, known-issues #4
- **Description**: Timeout/failed spawns can produce empty `stderr.log` and `output.jsonl` (0 bytes) with no extracted report. Users cannot distinguish harness startup failure vs timeout vs wrapper error.
- **Direction**: Ensure finalize path persists minimal structured failure artifact (`error_code`, `failure_reason`, timeout marker) even when harness emits no output.

### BUG-6: Large-file spawn fails with E2BIG
- **Source**: migration-notes line 14
- **Description**: Spawns with large reference files fail before model invocation with `OSError: [Errno 7] Argument list too long`. Switching to stdin transport and path-only `--file` references works around it, but the default path should handle this gracefully.

## Low

### BUG-7: Duplicate skill warnings from overlapping skill paths
- **Source**: known-issues #7
- **Description**: Overlapping local and bundled skill paths produce noisy duplicate warnings during skill resolution.
