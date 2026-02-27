# Task 7: Refactor God-Object Modules

**Status:** done

## Context

From the post-sandbox cleanup plan, Task 7 addresses SRP violations in large modules. After exploring the actual code, only **7a (run.py)** and **7d (agent.py)** warrant refactoring. The others are well-structured.

## Scope Decision

| Subtask | File | Lines | Verdict |
|---------|------|-------|---------|
| 7a | `ops/run.py` | 1,306 | **REFACTOR** — 6 distinct responsibility groups, 14+ dataclasses + validation + execution + queries + registration |
| 7b | `exec/spawn.py` | 727 | **SKIP** — 7 groups but well-cohesive; each serves `execute_with_finalization()`. Split would add indirection without reducing complexity. |
| 7c | `workspace/launch.py` | 465 | **SKIP** — 7 groups but all serve `launch_supervisor()`. Cohesive single-purpose module. |
| 7d | `config/agent.py` | 244 | **MINOR FIX** — one lazy import coupling point (`_known_mcp_tools` → `ops.get_all_operations`). Move to a static registry constant. |

## Task 7a: Split `ops/run.py` (1,306 → ~5 files)

### Current Responsibility Groups

1. **Data models** (lines 64–300): 10 dataclasses (`RunCreateInput`, `RunActionOutput`, `RunListInput`, etc.) + internal types (`_PreparedCreate`, `_CreateRuntimeView`, `RunListFilters`)
2. **Validation & assembly** (lines 302–580): `_validate_requested_model`, `_validate_create_input`, `_build_create_payload` (170-line function), model/profile/skill/permission/budget resolution
3. **State queries** (lines 582–680): `_read_run_row`, `_read_report_text`, `_read_files_touched`, `_detail_from_row`
4. **Execution core** (lines 685–915): `_run_child_env`, `_workspace_spend_usd`, `_execute_run_blocking`, `_execute_run_non_blocking`, `_track_task`
5. **Operation handlers** (lines 917–1220): `run_create[_sync]`, `run_list[_sync]`, `run_show[_sync]`, `run_wait[_sync]`, `run_continue[_sync]`, `run_retry[_sync]` — 12 functions
6. **Operation registration** (lines 1224–1307): 6 `operation(OperationSpec(...))` calls

### Proposed Split

```
ops/
├── __init__.py          (unchanged — lazy re-exports)
├── registry.py          (unchanged)
├── _runtime.py          (unchanged)
├── run.py               (SLIMMED — keep groups 5+6: operation handlers + registration)
├── _run_models.py       (NEW — group 1: all dataclasses)
├── _run_prepare.py      (NEW — group 2: validation + payload assembly)
├── _run_query.py        (NEW — group 3: state queries + detail formatting)
└── _run_execute.py      (NEW — group 4: execution core)
```

### File Contents

**`_run_models.py`** (~220 lines)
- Public dataclasses: `RunCreateInput`, `RunActionOutput`, `RunListInput`, `RunListEntry`, `RunListOutput`, `RunShowInput`, `RunDetailOutput`, `RunContinueInput`, `RunRetryInput`, `RunWaitInput`
- Internal types: `RunListFilters`
- Helper: `_empty_template_vars()`
- Note: `_PreparedCreate` and `_CreateRuntimeView` stay in `_run_prepare.py` (only used there)

**`_run_prepare.py`** (~300 lines)
- Internal types: `_PreparedCreate`, `_CreateRuntimeView` (co-located with their sole consumer)
- `_normalize_skill_flags`, `_looks_like_alias_identifier`
- `_validate_requested_model`, `_validate_create_input`
- `_load_model_guidance_text`, `_merge_warnings`
- `_build_create_payload` (the big 170-line assembly function)

**`_run_query.py`** (~100 lines)
- `_read_run_row`, `_read_report_text`, `_read_files_touched`
- `_detail_from_row` (DB row → RunDetailOutput conversion)
- `_build_run_list_query`

**`_run_execute.py`** (~250 lines)
- `_read_non_negative_int_env`, `_depth_limits` (used by execution, not just preparation)
- `_emit_subrun_event`, `_depth_exceeded_output` (execution-path helpers)
- `_run_child_env`, `_workspace_spend_usd`
- `_execute_run_blocking`, `_execute_run_non_blocking`
- `_track_task`

**`run.py`** (slimmed to ~400 lines)
- Imports from `_run_models`, `_run_prepare`, `_run_query`, `_run_execute`
- 12 operation handler functions (`run_create[_sync]`, etc.)
- 6 operation registrations at module bottom
- `_with_command`, `_prompt_for_follow_up`, `_run_is_terminal` (small helpers used only by handlers)

### Migration Rules

1. All new files are `_`-prefixed (private to the package).
2. `run.py` imports from siblings — no external import changes needed.
3. No public API changes — all external callers still import from `meridian.lib.ops.run`.
4. Tests don't directly import private `_run_*` modules.

### Dependency Flow

```
_run_models.py  ← pure dataclasses, no internal deps
     ↑
_run_prepare.py ← imports _run_models, config/*, prompt/*, safety/*
_run_query.py   ← imports _run_models, sqlite3, pathlib (no cross-dep with prepare)
_run_execute.py ← imports _run_models, exec/spawn, safety/* (no dep on _run_prepare)
     ↑
run.py          ← imports all _run_* modules, wires handlers + registration
```

Note: `_run_execute` does NOT import `_run_prepare`. Shared helpers (`_read_non_negative_int_env`, `_depth_limits`, `_emit_subrun_event`) live in `_run_execute` to avoid layering coupling.

---

## Task 7d: Decouple `config/agent.py` from ops

### Current Problem

```python
# config/agent.py:~line 60
@lru_cache(maxsize=1)
def _known_mcp_tools() -> frozenset[str]:
    from meridian.lib.ops import get_all_operations
    return frozenset(op.mcp_name for op in get_all_operations() if not op.cli_only)
```

Config layer lazily imports runtime ops layer for validation. Works but violates DIP.

### Reviewer Finding

Simply changing the import target from `ops.__init__` to `ops.registry` doesn't help — `registry.py` calls `_bootstrap_operation_modules()` at module level (line 86), which imports ALL ops modules. The coupling surface is the same either way.

### Fix (two-part)

**Part 1: Make registry bootstrap lazy** — defer `_bootstrap_operation_modules()` to first query:

```python
# ops/registry.py
_bootstrapped = False

def _ensure_bootstrapped() -> None:
    global _bootstrapped
    if _bootstrapped:
        return
    # Bootstrap first, then set flag. If bootstrap raises, next call retries.
    _bootstrap_operation_modules()
    _bootstrapped = True

def get_all_operations() -> list[OperationSpec[Any, Any]]:
    _ensure_bootstrapped()
    return [_REGISTRY[name] for name in sorted(_REGISTRY)]

def get_operation(name: str) -> OperationSpec[Any, Any]:
    _ensure_bootstrapped()
    return _REGISTRY[name]

def get_mcp_tool_names() -> frozenset[str]:
    _ensure_bootstrapped()
    return frozenset(s.mcp_name for s in _REGISTRY.values() if not s.cli_only)

# Remove the module-level _bootstrap_operation_modules() call
```

**Safety notes** (from reviewer):
- Flag is set AFTER bootstrap succeeds — if bootstrap raises, next call retries
- `get_operation()` also calls `_ensure_bootstrapped()` to prevent KeyError on first-call

**Part 2: Update agent.py** to use the narrower import:

```python
@lru_cache(maxsize=1)
def _known_mcp_tools() -> frozenset[str]:
    from meridian.lib.ops.registry import get_mcp_tool_names
    return get_mcp_tool_names()
```

Now importing `registry.py` is cheap (no bootstrap side effect). The bootstrap only runs when someone first queries operations. The lazy import in `agent.py` + `lru_cache` means the cost is paid exactly once, at first profile load.

### Risk

Making bootstrap lazy changes initialization order. All current callers (`cli/main.py`, MCP server, DirectAdapter) call `get_all_operations()` early in startup, so the bootstrap still happens before any operation is used. Add a test that verifies `get_all_operations()` returns non-empty to catch accidental bootstrap bypass.

---

## Verification

After implementation:
1. `uv run pytest -x -q` — all tests pass
2. `uv run meridian --version` — CLI loads
3. `uv run python -c "from meridian.lib.ops.run import run_create"` — public imports work
4. No new import cycles
