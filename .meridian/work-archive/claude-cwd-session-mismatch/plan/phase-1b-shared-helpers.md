# Phase 1b: Extract Shared CWD Predicate + Promote Claude Slug (R1 + R2)

## Scope

Two small refactorings that create shared helpers consumed by later phases:

1. **R1**: Extract the CLAUDECODE+Claude CWD-flip condition from `runner.py` into a shared helper so Phase 2a can reuse it in `execute.py` without duplicating the logic.
2. **R2**: Promote `_project_slug()` from private to public in `claude.py` so Phase 4 can import it for session symlink path encoding.

Both are behavior-preserving refactorings. No functional changes.

## Files to Modify

### NEW `src/meridian/lib/launch/cwd.py`

Create a new module with the shared CWD predicate:

```python
"""Shared CWD resolution for child spawn processes."""

import os
from pathlib import Path

from meridian.lib.core.types import HarnessId
from meridian.lib.state.paths import resolve_spawn_log_dir


def resolve_child_execution_cwd(
    repo_root: Path,
    spawn_id: str,
    harness_id: str,
) -> Path:
    """Determine the actual CWD for a child spawn process.

    When running Claude Code inside Claude Code (CLAUDECODE env set), the child
    process runs from the spawn log directory to avoid task output file collisions.
    See runner.py execute_with_finalization() for the authoritative site.

    This helper mirrors the runner.py condition so execute.py can pre-compute the
    value before session_scope entry. Both sites MUST stay in sync.
    """
    if os.environ.get("CLAUDECODE") and harness_id == HarnessId.CLAUDE.value:
        return resolve_spawn_log_dir(repo_root, spawn_id)
    return repo_root
```

### `src/meridian/lib/launch/runner.py`

1. **Import** the shared helper:
   ```python
   from meridian.lib.launch.cwd import resolve_child_execution_cwd
   ```

2. **Replace the inline condition** (lines 661-664). Currently:
   ```python
   if os.environ.get("CLAUDECODE") and harness.id == HarnessId.CLAUDE:
       child_cwd = log_dir
       child_cwd.mkdir(parents=True, exist_ok=True)
       command = (*command, "--add-dir", str(execution_cwd))
   ```

   Becomes:
   ```python
   resolved_cwd = resolve_child_execution_cwd(
       repo_root=execution_cwd,  # execution_cwd is repo_root at this point
       spawn_id=run.spawn_id,
       harness_id=harness.id.value,
   )
   if resolved_cwd != execution_cwd:
       child_cwd = resolved_cwd
       child_cwd.mkdir(parents=True, exist_ok=True)
       command = (*command, "--add-dir", str(execution_cwd))
   ```

   Note: `execution_cwd` in runner.py's scope is the repo_root passed as the `cwd` parameter. The variable name is confusing but existing -- don't rename it in this phase.

### `src/meridian/lib/harness/claude.py`

1. **Rename** `_project_slug()` (line 58) to `project_slug()` -- remove the leading underscore.
2. **Update internal callers** within claude.py: `_claude_project_dir()` (line 62-63) uses `_project_slug` -- update to `project_slug`.
3. **Add to `__all__`** if the module has one, or add a brief docstring noting it's a public API for session path encoding.

## Dependencies

- **Requires**: Nothing.
- **Produces**: `resolve_child_execution_cwd()` consumed by Phase 2a. `project_slug()` consumed by Phase 4.

## Patterns to Follow

- `launch/cwd.py` follows the same module pattern as other `launch/` helpers (e.g., `launch/session_scope.py`).
- The `__init__.py` for `launch/` should NOT re-export the helper -- import directly from the module.

## Constraints

- `resolve_child_execution_cwd()` MUST use `HarnessId.CLAUDE.value` (string comparison) since `execute.py` passes `prepared.harness_id` which is a string.
- `runner.py` compares against `harness.id` (a `HarnessId` enum). The helper accepts a string to work for both callers.
- The behavior of the CWD-flip MUST NOT change. The refactoring is purely extracting existing logic into a shared location.
- `project_slug()` encoding (`str(path.resolve()).replace("/", "-")`) MUST NOT change. Phase 4 depends on it matching Claude Code's actual project directory naming.

## Verification Criteria

- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes (0 errors)
- [ ] `uv run pytest-llm` passes
- [ ] `resolve_child_execution_cwd()` returns `repo_root` when `CLAUDECODE` is not set
- [ ] `resolve_child_execution_cwd()` returns log dir when `CLAUDECODE` is set and harness is Claude
- [ ] `resolve_child_execution_cwd()` returns `repo_root` when `CLAUDECODE` is set but harness is not Claude
- [ ] `runner.py` uses `resolve_child_execution_cwd()` instead of inline condition
- [ ] `project_slug()` is importable from `claude.py` (no leading underscore)
- [ ] Internal callers in `claude.py` use the renamed function
