# Design: SOLID & Consistency Refactor

Comprehensive refactor addressing findings from the state-safety, SOLID/extensibility, and consistency reviews. The goal: shared implementations, consistent patterns, and clean extension points.

## Overview

Twelve targeted refactors, ordered by dependency and impact. Each phase is independently shippable and testable.

| Phase | Focus | Risk | Files touched |
|-------|-------|------|---------------|
| 1 | Dead code & quick fixes | Low | 4 |
| 2 | Shared JSONL event store | Medium | 5 |
| 3 | Unified error semantics | Low | 4 |
| 4 | Ops helper consolidation | Low | 8 |
| 5 | Async wrapper consistency | Low | 4 |
| 6 | Session lifecycle extraction | Medium | 3 |
| 7 | Harness adapter ISP | Medium | 7 |
| 8 | CLI registration consolidation | Low | 8 |
| 9 | Session lock-order fix | Medium | 1 |
| 10 | PID-before-fork & launch mutex | Medium | 4 |
| 11 | Spawn state machine | Medium | 6 |
| 12 | Stale detection & reused chat IDs | Low | 2 |

---

## Phase 1: Dead Code & Quick Fixes

Remove dead code and fix the one-liner consistency gap that can crash read paths.

### 1a. Fix `spawn_store._parse_event` validation gap

**Problem:** `session_store._parse_event` catches `ValidationError` and returns `None`. `spawn_store._parse_event` does not. A single malformed event crashes `list_spawns()`, `get_spawn()`, `spawn show`, `spawn wait`, and the dashboard.

**Fix:**

```python
# src/meridian/lib/state/spawn_store.py
from pydantic import ValidationError

def _parse_event(payload: dict[str, Any]) -> SpawnEvent | None:
    event_type = payload.get("event")
    try:
        if event_type == "start":
            return SpawnStartEvent.model_validate(payload)
        if event_type == "update":
            return SpawnUpdateEvent.model_validate(payload)
        if event_type == "finalize":
            return SpawnFinalizeEvent.model_validate(payload)
    except ValidationError:
        return None
    return None
```

### 1b. Remove dead code

Remove these unused artifacts:

1. **`SpawnListFilters`** in `src/meridian/lib/ops/spawn/models.py` (lines 346-355) -- never imported anywhere. The docstring references "parameterized SQL" which no longer exists.

2. **`resolve_state_root()`** in `src/meridian/lib/ops/runtime.py` (lines 70-72) -- unused wrapper around `resolve_state_paths().root_dir`. Every call site already uses the direct path.

---

## Phase 2: Shared JSONL Event Store

**Problem:** `spawn_store.py` and `session_store.py` independently implement identical JSONL mechanics: file locking, event appending, line-by-line parsing with truncation recovery, and event dispatch. They've already drifted (ValidationError handling). Any future JSONL store will copy-paste again.

**Solution:** Extract a generic `JSONLEventStore` that owns the shared mechanics. Each domain store becomes a thin layer on top.

### New file: `src/meridian/lib/state/event_store.py`

```python
"""Generic JSONL event store with locking, append, and crash-tolerant reads."""

from __future__ import annotations

import fcntl
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from meridian.lib.state.atomic import append_text_line

T = TypeVar("T", bound=BaseModel)


@contextmanager
def lock_file(lock_path: Path):
    """Acquire an exclusive advisory lock on a sidecar lock file."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, "w")  # noqa: SIM115
    try:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield handle
    finally:
        fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()


def append_event(
    data_path: Path,
    lock_path: Path,
    event: BaseModel,
) -> None:
    """Serialize and append a single event under exclusive lock."""
    line = json.dumps(
        event.model_dump(mode="json"),
        separators=(",", ":"),
        sort_keys=True,
    )
    with lock_file(lock_path):
        append_text_line(data_path, line)


def read_events(
    data_path: Path,
    parse_event: Callable[[dict[str, Any]], T | None],
) -> list[T]:
    """Read all events from a JSONL file, tolerating truncation and validation errors.

    - Malformed JSON on the last line is silently skipped (interrupted write recovery).
    - Events that fail schema validation are silently skipped (forward compatibility).
    - All other lines are parsed via the caller-supplied dispatch function.
    """
    if not data_path.is_file():
        return []

    text = data_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    events: list[T] = []

    for index, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            if index == len(lines) - 1:
                continue  # Truncated trailing append -- self-healing.
            continue  # Mid-file corruption -- skip silently.

        parsed = parse_event(payload)
        if parsed is not None:
            events.append(parsed)

    return events
```

The `Callable` import is missing above -- add `from collections.abc import Callable`.

### Refactored `spawn_store.py` (relevant parts)

```python
from meridian.lib.state.event_store import append_event, lock_file, read_events

def _parse_event(payload: dict[str, Any]) -> SpawnEvent | None:
    event_type = payload.get("event")
    try:
        if event_type == "start":
            return SpawnStartEvent.model_validate(payload)
        if event_type == "update":
            return SpawnUpdateEvent.model_validate(payload)
        if event_type == "finalize":
            return SpawnFinalizeEvent.model_validate(payload)
    except ValidationError:
        return None
    return None

# Replace _read_events() with:
def _read_events(state_root: Path) -> list[SpawnEvent]:
    paths = resolve_state_paths(state_root)
    return read_events(paths.spawns_jsonl, _parse_event)

# Replace _append_event() with:
def _append_spawn_event(state_root: Path, event: BaseModel) -> None:
    paths = resolve_state_paths(state_root)
    append_event(paths.spawns_jsonl, paths.spawns_lock, event)
```

### Refactored `session_store.py` (relevant parts)

Same pattern. Replace `_lock_file`, `_append_event`, `_read_events` with calls to the shared `event_store` module.

### What stays domain-specific

- **Event type definitions** (SpawnStartEvent, SessionStartEvent, etc.)
- **State reconstruction** (_record_from_events, _records_by_session) -- different fold logic per domain
- **Session lifetime locks** (_SESSION_LOCK_HANDLES) -- session-specific concern, stays in session_store
- **Query/filter functions** -- domain-specific

### Impact

- Eliminates ~150 lines of duplicated locking/parsing/appending code
- Guarantees consistent truncation recovery and validation error handling
- Future JSONL stores (e.g., audit log) get the same guarantees for free

---

## Phase 3: Unified Error Semantics

**Problem:** The state layer uses three different patterns for "resource not found":
- `get_work_item()` returns `None`
- `update_work_item()` raises `KeyError`
- `rename_work_item()` raises `ValueError`

The CLI then special-cases `KeyError` formatting to avoid Python repr noise. Callers can't predict which exception to catch.

**Convention:**

| Operation | Not found | Validation error |
|-----------|-----------|-----------------|
| Pure getter | Return `None` | Return `None` |
| Mutation (update, rename, delete) | Raise `ValueError` | Raise `ValueError` |

`ValueError` is already used by `rename_work_item` and is the natural Python choice for "this operation can't proceed because the input is invalid." `KeyError` implies dict-like semantics that don't match a directory-backed store.

### Changes to `work_store.py`

```python
def update_work_item(
    state_root: Path,
    work_id: str,
    *,
    status: str | None = None,
    description: str | None = None,
    auto_generated: bool | None = None,
) -> WorkItem:
    current = get_work_item(state_root, work_id)
    if current is None:
        raise ValueError(f"Work item '{work_id}' not found")  # was KeyError

    # ... rest unchanged
```

### CLI error handling simplification

The CLI currently catches `KeyError` separately:

```python
# Before (cli/main.py)
except KeyError as exc:
    emit_error(str(exc).strip("'\""))  # Strip Python repr quotes
```

After the change, all store mutations raise `ValueError` with human-readable messages. The CLI catches `ValueError` uniformly:

```python
# After
except ValueError as exc:
    emit_error(str(exc))
```

### `collect_active_chat_ids` return type

**Problem:** Returns `None` on OSError, `frozenset[str]` otherwise. Callers must handle two types.

**Fix:** Return empty `frozenset()` on error instead of `None`. The semantics are the same -- "we don't know of any active sessions" -- but the type is uniform.

```python
def collect_active_chat_ids(repo_root: Path) -> frozenset[str]:
    """Return chat IDs with unclosed sessions. Empty set on error."""
    try:
        ...
    except OSError:
        return frozenset()
```

---

## Phase 4: Ops Helper Consolidation

**Problem:** `_runtime_context()`, `_state_root()`, `_resolve_chat_id()`, and `_resolve_roots()` are duplicated across 6+ ops modules with subtle differences. `_resolve_chat_id` in `work.py` accepts a `payload_chat_id` parameter; in `spawn/execute.py` it defaults to `"c0"`; in `work.py` it returns an empty string for missing context.

**Solution:** Move shared helpers to `src/meridian/lib/ops/runtime.py` (which already exists and is underused).

### New helpers in `ops/runtime.py`

```python
def resolve_runtime_context(ctx: RuntimeContext | None) -> RuntimeContext:
    """Return the provided context or resolve from environment."""
    if ctx is not None:
        return ctx
    return RuntimeContext.from_environment()


def resolve_state_root(repo_root: Path) -> Path:
    """Resolve the .meridian state root for a repository."""
    return resolve_state_paths(repo_root).root_dir


def resolve_repo_and_state(repo_root: str | None) -> tuple[Path, Path]:
    """Resolve both repo root and state root from an optional path string."""
    resolved_repo, _ = resolve_runtime_root_and_config(repo_root)
    return resolved_repo, resolve_state_paths(resolved_repo).root_dir


def resolve_chat_id(
    *,
    payload_chat_id: str = "",
    ctx: RuntimeContext | None = None,
    fallback: str = "",
) -> str:
    """Resolve a chat ID from an explicit payload value or runtime context.

    Resolution order: payload_chat_id > ctx.chat_id > fallback.
    """
    if payload_chat_id.strip():
        return payload_chat_id.strip()
    if ctx is not None and ctx.chat_id:
        return ctx.chat_id.strip()
    return fallback
```

### Migration

Replace all per-module copies:
- `spawn/api.py:_runtime_context` -> `from meridian.lib.ops.runtime import resolve_runtime_context`
- `spawn/api.py:_state_root` -> `from meridian.lib.ops.runtime import resolve_state_root`
- `spawn/query.py:_state_root` -> same
- `diag.py:_state_root` -> same
- `work.py:_runtime_context` -> same
- `work.py:_resolve_roots` -> `from meridian.lib.ops.runtime import resolve_repo_and_state`
- `work.py:_resolve_chat_id` -> `from meridian.lib.ops.runtime import resolve_chat_id`
- `report.py:_runtime_context` -> same
- `spawn/execute.py:_runtime_context` -> same
- `spawn/execute.py:_resolve_chat_id` -> `resolve_chat_id(..., fallback="c0")`

The `fallback` parameter unifies the divergent defaults: `work.py` uses `fallback=""`, `execute.py` uses `fallback="c0"`.

### Impact

- Eliminates 6 duplicate function definitions
- Makes the divergent `_resolve_chat_id` defaults explicit via parameter
- Single place to evolve resolution logic

---

## Phase 5: Async Wrapper Consistency

**Problem:** Ops modules expose async functions on the MCP surface. Some use `asyncio.to_thread()` to avoid blocking the event loop; others call sync implementations directly, blocking the MCP server.

| Module | Pattern | Blocks event loop? |
|--------|---------|-------------------|
| `spawn/api.py` | `await asyncio.to_thread(sync_fn, ...)` | No |
| `config.py` | `await asyncio.to_thread(sync_fn, ...)` | No |
| `diag.py` | `await asyncio.to_thread(sync_fn, ...)` | No |
| `report.py` | `return sync_fn(...)` | **Yes** |
| `work.py` | `return sync_fn(...)` | **Yes** |
| `catalog.py` | `return sync_fn(...)` | **Yes** |

**Solution:** Standardize on `asyncio.to_thread` for all async wrappers. Better yet, generate them from a single pattern.

### Option A: Helper decorator (preferred)

```python
# src/meridian/lib/ops/runtime.py

def async_from_sync(sync_fn: Callable[P, T]) -> Callable[P, Coroutine[Any, Any, T]]:
    """Create an async wrapper that runs a sync function in a thread."""
    @functools.wraps(sync_fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        return await asyncio.to_thread(sync_fn, *args, **kwargs)
    return wrapper
```

Usage in ops modules:

```python
# src/meridian/lib/ops/work.py
from meridian.lib.ops.runtime import async_from_sync

work_start = async_from_sync(work_start_sync)
work_list = async_from_sync(work_list_sync)
work_show = async_from_sync(work_show_sync)
# ... etc
```

### Option B: Generate in manifest registration

Make the manifest accept only sync handlers and auto-wrap them for MCP:

```python
# In manifest.py, when building MCP handlers:
if op.sync_handler and not op.handler:
    op = op._replace(handler=async_from_sync(op.sync_handler))
```

Option A is simpler and more explicit. Option B is more automatic but changes the manifest contract.

### Impact

- Fixes event-loop blocking for `report.*`, `work.*`, `catalog.*` MCP operations
- Eliminates boilerplate async wrapper functions (~60 lines across 3 modules)
- Single pattern to maintain

---

## Phase 6: Session Lifecycle Extraction

**Problem:** `_session_execution_context` (spawn/execute.py) and `run_harness_process` (launch/process.py) both implement session start/stop, auto-work creation, materialization cleanup, and harness session ID observation. They're already close but not identical, and they'll drift further as new session-level concerns are added.

**Solution:** Extract a `SessionScope` context manager that owns the shared lifecycle. Let each call site compose it with transport-specific concerns.

### New file: `src/meridian/lib/state/session_scope.py`

```python
"""Shared session lifecycle scope for primary launch and child spawn execution."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from meridian.lib.state import work_store
from meridian.lib.state.session_store import (
    get_session_active_work_id,
    start_session,
    stop_session,
    update_session_work_id,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SessionScopeResult:
    """Resolved values from session startup."""
    chat_id: str
    work_id: str | None


@contextmanager
def session_scope(
    state_root: Path,
    *,
    harness: str,
    harness_session_id: str | None = None,
    model: str = "",
    chat_id: str | None = None,
    agent: str = "",
    agent_path: str = "",
    skills: tuple[str, ...] = (),
    skill_paths: tuple[str, ...] = (),
) -> Iterator[SessionScopeResult]:
    """Manage session start, auto-work creation, and session stop.

    On entry:
      1. Starts the session (acquires lifetime lock).
      2. Auto-creates a work item if the session has none.
    On exit:
      3. Stops the session (releases lifetime lock).

    Transport-specific concerns (lock files, PID tracking, materialization)
    remain the caller's responsibility.
    """
    resolved_chat_id = start_session(
        state_root,
        harness=harness,
        harness_session_id=harness_session_id,
        model=model,
        chat_id=chat_id,
        agent=agent,
        agent_path=agent_path,
        skills=skills,
        skill_paths=skill_paths,
    )

    # Auto-create work item if session has none.
    work_id = get_session_active_work_id(state_root, resolved_chat_id)
    if not work_id:
        auto_item = work_store.create_auto_work_item(state_root)
        update_session_work_id(state_root, resolved_chat_id, auto_item.name)
        work_id = auto_item.name

    try:
        yield SessionScopeResult(chat_id=resolved_chat_id, work_id=work_id)
    finally:
        try:
            stop_session(state_root, resolved_chat_id)
        except Exception:
            logger.warning(
                "Failed to stop session %s cleanly.", resolved_chat_id, exc_info=True
            )
```

### Integration: spawn/execute.py

```python
from meridian.lib.state.session_scope import session_scope

@contextmanager
def _session_execution_context(...) -> Iterator[_SessionExecutionContext]:
    with session_scope(
        state_root,
        harness=harness_id,
        harness_session_id=harness_session_id,
        model=model,
        agent=session_agent,
        agent_path=session_agent_path,
        skills=skills,
        skill_paths=session_skill_paths,
    ) as scope:
        # Transport-specific: resolve agent materialization
        resolved_agent_name = _materialize_session_agent_name(...)
        try:
            yield _SessionExecutionContext(
                chat_id=scope.chat_id,
                resolved_agent_name=resolved_agent_name,
                ...
            )
        finally:
            _cleanup_session_materialized(...)
```

### Integration: launch/process.py

```python
from meridian.lib.state.session_scope import session_scope

def run_harness_process(ctx, request, ...):
    with session_scope(
        ctx.state_root,
        harness=ctx.session_metadata.harness,
        harness_session_id=ctx.seed_harness_session_id,
        model=ctx.session_metadata.model,
        chat_id=request.continue_chat_id,
        agent=ctx.session_metadata.agent,
        agent_path=ctx.session_metadata.agent_path,
        skills=ctx.session_metadata.skills,
        skill_paths=ctx.session_metadata.skill_paths,
    ) as scope:
        chat_id = scope.chat_id
        # Transport-specific: primary spawn, lock files, PID tracking, etc.
        ...
```

### Also extract: materialization cleanup

```python
# src/meridian/lib/state/session_scope.py (or a small helper module)

def cleanup_materialized_resources(
    *,
    harness_id: str,
    repo_root: Path,
    harness_registry: HarnessRegistry,
) -> None:
    """Clean up materialized harness resources. Logs warnings on failure."""
    normalized = harness_id.strip()
    if not normalized:
        return
    try:
        cleanup_materialized(normalized, repo_root, registry=harness_registry)
    except Exception:
        logger.warning(
            "Failed to cleanup materialized resources for harness %s.",
            normalized,
            exc_info=True,
        )
```

This replaces both `_cleanup_session_materialized` (execute.py) and `_cleanup_launch_materialized` (process.py), which are identical.

### Impact

- Session start/stop and auto-work creation defined once
- Adding session-level concerns (e.g., pinned artifacts, session metadata) requires editing one file
- Transport-specific concerns (lock files, PID tracking, materialization) stay where they belong

---

## Phase 7: Harness Adapter ISP

**Problem:** `HarnessAdapter` is a 15+ method protocol mixing subprocess launch, stream parsing, session detection, and in-process execution. `DirectAdapter` stubs out most methods with fake returns. Adding another non-subprocess harness will require more fake methods.

**Solution:** Split into focused protocols. Each adapter implements only the protocols it supports.

### Protocol hierarchy

```python
# src/meridian/lib/harness/adapter.py

class HarnessIdentity(Protocol):
    """Every harness has an identity and capabilities."""
    @property
    def id(self) -> HarnessId: ...
    @property
    def capabilities(self) -> HarnessCapabilities: ...


class SubprocessHarness(HarnessIdentity, Protocol):
    """Harness that launches a CLI subprocess."""
    def build_command(self, run: SpawnParams, perms: PermissionConfig) -> list[str]: ...
    def env_overrides(self, config: PermissionConfig) -> dict[str, str]: ...
    def blocked_child_env_vars(self) -> frozenset[str]: ...
    def mcp_config(self, run: SpawnParams) -> McpConfig | None: ...


class StreamParsingHarness(Protocol):
    """Harness that emits parseable stream events."""
    def parse_stream_event(self, line: str) -> StreamEvent | None: ...
    def extract_usage(self, artifacts: Path, spawn_id: str) -> TokenUsage: ...
    def extract_report(self, artifacts: Path, spawn_id: str) -> str | None: ...
    def extract_session_id(self, artifacts: Path, spawn_id: str) -> str | None: ...


class SessionAwareHarness(Protocol):
    """Harness with session lifecycle support."""
    def seed_session(self, is_resume: bool, harness_session_id: str | None, passthrough_args: list[str]) -> SessionSeed: ...
    def filter_launch_content(self, prompt: str, skill_injection: str, is_resume: bool, harness_session_id: str | None) -> PromptPolicy: ...
    def detect_primary_session_id(self, repo_root: Path, started_at_epoch: float, started_at_local_iso: str) -> str | None: ...
    def owns_untracked_session(self, repo_root: Path, session_ref: str) -> bool: ...


class InProcessHarness(HarnessIdentity, Protocol):
    """Harness that executes in-process (no subprocess)."""
    async def execute(self, ...) -> SpawnResult: ...
```

### Adapter changes

**ClaudeAdapter, CodexAdapter, OpenCodeAdapter:** Implement `SubprocessHarness + StreamParsingHarness + SessionAwareHarness`. No changes to method signatures -- they already implement all of these.

**DirectAdapter:** Implements only `InProcessHarness`. Drops the fake `build_command()`, `parse_stream_event()`, etc.

### BaseHarnessAdapter stays

`BaseHarnessAdapter` continues to provide sensible defaults for optional methods (`extract_tasks`, `extract_findings`, `native_layout`, `run_prompt_policy`). The subprocess adapters inherit from it. `DirectAdapter` does not.

### Registry changes

The registry currently returns a single `HarnessAdapter` type. After the split:

```python
class HarnessRegistry:
    def get_subprocess_adapter(self, harness_id: str) -> SubprocessHarness: ...
    def get_in_process_adapter(self, harness_id: str) -> InProcessHarness: ...
    def get_adapter(self, harness_id: str) -> HarnessIdentity: ...
```

The launch pipeline calls `get_subprocess_adapter()` and gets type-safe access to subprocess methods. Direct mode calls `get_in_process_adapter()`.

### Impact

- `DirectAdapter` no longer needs fake subprocess methods
- New non-subprocess harnesses (e.g., API-backed, container-based) only implement relevant protocols
- Launch code is type-safe: can't accidentally call `build_command()` on a direct adapter
- Existing subprocess adapters require minimal changes (they already implement all methods)

---

## Phase 8: CLI Registration Consolidation

**Problem:** 7 CLI modules repeat an identical ~70-line registration pattern: define handler dict, query manifest, match by group, register with cyclopts.

**Solution:** Extract a generic `register_cli_group()` function.

### New helper: `src/meridian/cli/registry.py`

```python
"""Generic CLI group registration from the ops manifest."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any

from cyclopts import App

from meridian.lib.ops.manifest import get_operations_for_surface


def register_cli_group(
    app: App,
    group: str,
    handlers: dict[str, Callable[[], Callable[..., None]]],
    *,
    default_command: str | None = None,
) -> tuple[set[str], dict[str, str]]:
    """Register CLI commands for a manifest group.

    Args:
        app: The cyclopts App (or sub-app) to register commands on.
        group: The manifest cli_group to filter by (e.g., "spawn", "work").
        handlers: Map of operation name -> factory returning the handler function.
        default_command: Optional operation name to set as the default command.

    Returns:
        Tuple of (registered command names, {op_name: description}).

    Raises:
        ValueError: If a manifest operation has no matching handler.
    """
    registered: set[str] = set()
    descriptions: dict[str, str] = {}

    for op in get_operations_for_surface("cli"):
        if op.cli_group != group:
            continue

        handler_factory = handlers.get(op.name)
        if handler_factory is None:
            raise ValueError(
                f"No CLI handler registered for operation '{op.name}' in group '{group}'"
            )

        handler = handler_factory()
        handler.__name__ = f"cmd_{op.cli_group}_{op.cli_name}"

        is_default = op.name == default_command
        app.command(handler, name=op.cli_name, help=op.description, default=is_default)

        registered.add(f"{op.cli_group}.{op.cli_name}")
        descriptions[op.name] = op.description

    return registered, descriptions
```

### Migration example (spawn.py)

```python
# Before: 30 lines of boilerplate
def register_spawn_commands(app: App, emit: Emitter) -> tuple[set[str], dict[str, str]]:
    handlers = {
        "spawn.files": lambda: partial(_spawn_files, emit),
        "spawn.list": lambda: partial(_spawn_list, emit),
        # ...
    }
    registered: set[str] = set()
    descriptions: dict[str, str] = {}
    for op in get_operations_for_surface("cli"):
        if op.cli_group != "spawn":
            continue
        handler_factory = handlers.get(op.name)
        if handler_factory is None:
            raise ValueError(...)
        handler = handler_factory()
        handler.__name__ = ...
        app.command(handler, ...)
        registered.add(...)
        descriptions[op.name] = op.description
    return registered, descriptions

# After: 1 call
def register_spawn_commands(app: App, emit: Emitter) -> tuple[set[str], dict[str, str]]:
    return register_cli_group(app, "spawn", {
        "spawn.files": lambda: partial(_spawn_files, emit),
        "spawn.list": lambda: partial(_spawn_list, emit),
        # ...
    }, default_command="spawn.create")
```

### Impact

- Eliminates ~400 lines of duplicated registration boilerplate (7 modules x ~60 lines)
- Consistent error handling for missing handlers
- Single place to evolve registration mechanics (e.g., add middleware, validation)

---

## Implementation Sequence

```
Phase 1  ─────────────────────────>  commit
    │
Phase 2  ─────────────────────────>  commit
    │
Phase 3  ──────>  commit
    │
Phase 4  ──────>  commit        Phase 5  ──────>  commit
    │                                │
Phase 6  ─────────────────────────>  commit
    │
Phase 7  ─────────────────────────>  commit
    │
Phase 8  ──────>  commit
```

Phases 1-3 are prerequisites (they fix the state layer). Phases 4-5 are independent. Phase 6 depends on Phase 2 (uses shared session helpers). Phase 7 is independent. Phase 8 is independent. Phases 9-12 address the concurrency/safety findings and benefit from the cleaner abstractions established in Phases 1-8.

---

## Phase 9: Session Lock-Order Fix

**Problem:** `start_session()` and `stop_session()` acquire locks in order GLOBAL → PER-SESSION. But `cleanup_stale_sessions()` acquires them PER-SESSION → GLOBAL. This is a textbook lock-order inversion that can deadlock:

```
Process A (stopping session):                    Process B (cleanup):
  stop_session()                                   cleanup_stale_sessions()
    wants GLOBAL lock ← blocked                      holds GLOBAL lock
    holds PER-SESSION lock                            wants PER-SESSION lock ← blocked
                        ↑ DEADLOCK ↑
```

The deadlock hasn't been triggered in practice because `cleanup_stale_sessions()` uses `LOCK_NB` (non-blocking) for per-session locks, so it skips held locks rather than blocking. But the pattern is still dangerous: if `cleanup_stale_sessions` is ever called from a path that needs to wait (e.g., a "force cleanup" mode), or if a future change adds a blocking variant, the deadlock becomes live.

**Root cause:** The two-lock design mixes two concerns -- event-log serialization (global lock) and session-liveness signaling (per-session lock) -- without a strict acquisition order.

### Fix: Separate detection from mutation

The key insight is that `cleanup_stale_sessions()` doesn't need the global lock during detection -- it only needs it when writing stop events. And it doesn't need the per-session locks when writing -- it only needs them to identify stale sessions.

**Current flow (buggy order):**
```
1. For each *.lock file:
     Try LOCK_NB on per-session lock     ← acquires per-session
     If acquired → stale
2. With global lock:                      ← acquires global (INVERSION)
     Write stop events
     Delete lock files
3. Release per-session locks
```

**Fixed flow (consistent order):**
```
1. For each *.lock file:
     Try LOCK_NB on per-session lock
     If acquired → record as stale
     Release per-session lock immediately  ← don't hold across phases
2. With global lock:                       ← only lock held
     Write stop events
3. For each stale lock:
     Re-acquire per-session lock (NB)      ← safe: no global lock held
     Delete lock file
     Release
```

```python
def cleanup_stale_sessions(state_root: Path) -> list[str]:
    """Detect and clean up sessions whose owning process has died."""
    paths = resolve_state_paths(state_root)

    if not paths.sessions_dir.is_dir():
        return []

    # Phase 1: Detect stale sessions by probing per-session locks.
    # Release each lock immediately -- do NOT hold across phases.
    stale_chat_ids: list[str] = []
    for lock_path in paths.sessions_dir.glob("*.lock"):
        chat_id = lock_path.stem
        try:
            handle = lock_path.open("a+b")
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Acquired → no other process holds it → stale.
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                stale_chat_ids.append(chat_id)
            except BlockingIOError:
                pass  # Lock held → session is active.
            finally:
                handle.close()
        except OSError:
            continue

    if not stale_chat_ids:
        return []

    # Phase 2: Write stop events under global lock.
    # No per-session locks held here -- order is safe.
    stale_set = set(stale_chat_ids)
    with lock_file(paths.sessions_lock):
        records = _records_by_session(state_root)
        for chat_id in stale_chat_ids:
            existing = records.get(chat_id)
            if existing is not None and existing.stopped_at is None:
                _append_event(paths.sessions_jsonl, SessionStopEvent(
                    event="stop", chat_id=chat_id,
                ))

    # Phase 3: Delete stale lock files.
    # Re-probe each lock (NB) to confirm still stale before deleting.
    cleaned: list[str] = []
    for chat_id in stale_chat_ids:
        lock_path = paths.sessions_dir / f"{chat_id}.lock"
        try:
            handle = lock_path.open("a+b")
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                lock_path.unlink(missing_ok=True)
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                cleaned.append(chat_id)
            except BlockingIOError:
                pass  # Someone else grabbed it between phases -- skip.
            finally:
                handle.close()
        except OSError:
            continue

    # Phase 4: Clean up in-process handle references.
    for chat_id in cleaned:
        _SESSION_LOCK_HANDLES.pop(
            _session_lock_key(state_root, chat_id), None
        )

    return cleaned
```

### Why this is safe

- **No lock-order inversion:** Per-session locks are never held while the global lock is acquired. Each phase uses at most one lock type.
- **TOCTOU between phases:** A session could start between Phase 1 (detection) and Phase 3 (deletion). The re-probe in Phase 3 catches this: if the new session grabbed the lock, `LOCK_NB` fails and we skip the delete.
- **Stop event idempotence:** Writing a stop event for an already-stopped session is a no-op in the event fold (`_records_by_session` ignores duplicate stops).

### Also fix: `start_session()` event-before-lock gap

**Problem (Finding #4 from state-safety review):** `start_session()` appends the start event to `sessions.jsonl` before acquiring the per-session lifetime lock. If the process crashes between the event write and lock acquisition, the session is "logically active" forever -- `cleanup_stale_sessions()` only cleans up sessions that have a lock file.

**Fix:** Acquire the per-session lifetime lock first, then write the start event.

```python
def start_session(state_root: Path, *, harness: str, ...) -> str:
    paths = resolve_state_paths(state_root)
    resolved_chat_id = chat_id or _generate_chat_id()

    # 1. Acquire lifetime lock FIRST -- before recording anything.
    lock_path = paths.sessions_dir / f"{resolved_chat_id}.lock"
    handle = _acquire_session_lock(lock_path)
    _SESSION_LOCK_HANDLES[_session_lock_key(state_root, resolved_chat_id)] = handle

    # 2. Then record the start event under global lock.
    with lock_file(paths.sessions_lock):
        _append_event(paths.sessions_jsonl, SessionStartEvent(...))

    return resolved_chat_id
```

Now if the process crashes after step 1 but before step 2, the lock file exists and `cleanup_stale_sessions()` will detect and clean it up. If it crashes before step 1, nothing was recorded.

---

## Phase 10: PID-Before-Fork & Launch Mutex

Two related fixes: close the crash window where a child process exists but its PID isn't recorded, and make `active-primary.lock` an actual mutex.

### 10a. PID intent file: write before fork

**Problem:** All three launch paths (background wrapper, foreground primary, runner child) start the child process before writing the PID file. If meridian crashes between `Popen()`/`fork()` and the PID write, the child runs orphaned and the reaper can't find it.

The crash window is:
```
Popen()/fork()  →  [CRASH WINDOW]  →  write PID file  →  mark_spawn_running()
```

**Solution:** Write a **PID intent file** before forking, then update it with the actual PID after fork succeeds. The reaper can then distinguish "launcher still starting" from "launcher crashed after fork."

```python
# New convention: <spawn_dir>/launch_intent.json
# Written BEFORE fork. Updated AFTER fork. Checked by reaper.

def write_launch_intent(spawn_dir: Path, *, parent_pid: int) -> None:
    """Record that this process intends to launch a child. Written before fork."""
    atomic_write_text(spawn_dir / "launch_intent.json", json.dumps({
        "parent_pid": parent_pid,
        "child_pid": None,          # Not yet known.
        "started_at": _utc_now_iso(),
    }) + "\n")


def update_launch_intent(spawn_dir: Path, *, child_pid: int) -> None:
    """Record the child PID after successful fork."""
    intent_path = spawn_dir / "launch_intent.json"
    existing = json.loads(intent_path.read_text())
    existing["child_pid"] = child_pid
    atomic_write_text(intent_path, json.dumps(existing) + "\n")
```

**Launch sequence becomes:**

```python
# Background spawn (execute.py)
spawn_dir = resolve_spawn_log_dir(...)
spawn_dir.mkdir(parents=True, exist_ok=True)
write_launch_intent(spawn_dir, parent_pid=os.getpid())    # BEFORE fork

process = subprocess.Popen(launch_command, ...)

update_launch_intent(spawn_dir, child_pid=process.pid)     # AFTER fork
atomic_write_text(spawn_dir / "background.pid", f"{process.pid}\n")
mark_spawn_running(...)
```

**Reaper changes:**

When the reaper sees a missing PID file but `launch_intent.json` exists:
1. If `child_pid` is set → use it (same as reading the PID file).
2. If `child_pid` is None → check if `parent_pid` is alive.
   - Parent alive → still launching, respect grace period.
   - Parent dead → launcher crashed before fork completed. Safe to finalize as failed.

```python
def _inspect_spawn_runtime(record: SpawnRecord, spawn_dir: Path, ...) -> _SpawnInspection:
    # ... existing PID file checks ...

    # Fallback: check launch intent for crash-window recovery.
    if wrapper_pid is None and harness_pid is None:
        intent = _read_launch_intent(spawn_dir)
        if intent is not None:
            if intent.child_pid is not None:
                # Fork succeeded but PID file never written.
                # Use the intent's child_pid.
                if launch_mode == BACKGROUND_LAUNCH_MODE:
                    wrapper_pid = intent.child_pid
                    wrapper_alive = _pid_is_alive(wrapper_pid, ...)
                else:
                    harness_pid = intent.child_pid
                    harness_alive = _pid_is_alive(harness_pid, ...)
            elif intent.parent_pid is not None:
                # Fork never completed. Check if launcher is still alive.
                if _pid_is_alive(intent.parent_pid, ...):
                    # Launcher still running -- extend grace.
                    grace_elapsed = False
                # else: launcher dead, child never started.
                # Let normal grace-elapsed logic finalize it.
```

### 10b. Make `active-primary.lock` an actual mutex

**Problem:** `active-primary.lock` is a JSON status file, not a lock. Two primary launches can race without serialization.

**Fix:** Use `fcntl.flock` on the file in addition to writing status. The lock file becomes both a mutex and a status marker.

```python
# src/meridian/lib/launch/process.py

@contextmanager
def primary_launch_lock(lock_path: Path, *, command: tuple[str, ...]):
    """Acquire exclusive primary launch lock. Blocks if another primary is starting."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, "w")
    try:
        # Non-blocking first to give a better error message.
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            # Another primary launch is active. Could block or error.
            # For now, block with a timeout.
            fcntl.flock(handle, fcntl.LOCK_EX)

        # Write status payload (for observability, not mutual exclusion).
        payload = {
            "parent_pid": os.getpid(),
            "child_pid": None,
            "started_at": _utc_now_iso(),
            "command": list(command),
        }
        handle.write(json.dumps(payload) + "\n")
        handle.flush()

        yield handle  # Caller can update child_pid later.
    finally:
        fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()
```

Usage in `run_harness_process`:
```python
with primary_launch_lock(ctx.lock_path, command=command) as lock_handle:
    # ... fork child ...
    # Update child_pid in lock file after fork.
    _update_lock_child_pid(lock_handle, child_pid)
    # ... run until completion ...
# Lock released automatically on exit.
```

`cleanup_orphaned_locks()` continues to work: it tries `LOCK_NB` on the file. If the lock is held, the primary is alive. If acquired, the primary is dead and the lock is stale.

---

## Phase 11: Spawn State Machine

**Problem:** Spawn lifecycle states are partially centralized in `spawn_lifecycle.py`, but transition logic is spread across `spawn_store.py`, `runner.py`, `reaper.py`, `execute.py`, and `api.py`. Status checks use hardcoded strings (`== "running"`, `== "queued"`) in 15+ locations. Adding a new state (e.g., `retrying`, `paused`) requires coordinated edits across all these modules.

**Solution:** Define an explicit state machine with typed transitions in `spawn_lifecycle.py`. All status changes go through the machine. Direct string comparisons are replaced by predicates.

### State machine definition

```python
# src/meridian/lib/core/spawn_lifecycle.py

from __future__ import annotations

from enum import Enum
from typing import Literal

from meridian.lib.core.domain import SpawnStatus


class SpawnTransition(Enum):
    """All legal spawn state transitions."""
    # Normal lifecycle
    CREATE        = ("queued",)           # → queued (initial)
    START_RUNNING = ("queued", "running") # queued → running
    SUCCEED       = ("running", "succeeded")
    FAIL          = ("running", "failed")
    CANCEL        = ("running", "cancelled")

    # Recovery transitions (reaper)
    RECOVER_RUNNING   = ("queued", "running")    # reaper promotes queued → running
    RECOVER_SUCCEEDED = ("running", "succeeded") # reaper: durable report found
    RECOVER_FAILED    = ("running", "failed")    # reaper: orphan/stale
    FAIL_QUEUED       = ("queued", "failed")     # reaper: missing PID after grace

    def __init__(self, *states: str):
        if len(states) == 1:
            self._from_status = None
            self._to_status = states[0]
        else:
            self._from_status = states[0]
            self._to_status = states[1]

    @property
    def from_status(self) -> SpawnStatus | None:
        return self._from_status

    @property
    def to_status(self) -> SpawnStatus:
        return self._to_status


# Legal transitions as a lookup table.
_ALLOWED_TRANSITIONS: dict[SpawnStatus | None, frozenset[SpawnStatus]] = {
    None:        frozenset({"queued"}),                          # initial
    "queued":    frozenset({"running", "failed", "cancelled"}),  # start, fail, cancel
    "running":   frozenset({"succeeded", "failed", "cancelled"}),
    "succeeded": frozenset(),  # terminal
    "failed":    frozenset(),  # terminal
    "cancelled": frozenset(),  # terminal
}

TERMINAL_STATUSES: frozenset[SpawnStatus] = frozenset({"succeeded", "failed", "cancelled"})


def is_terminal(status: SpawnStatus) -> bool:
    """Return True if the status is a terminal (final) state."""
    return status in TERMINAL_STATUSES


def is_active(status: SpawnStatus) -> bool:
    """Return True if the status is an active (non-terminal) state."""
    return status not in TERMINAL_STATUSES


def validate_transition(from_status: SpawnStatus | None, to_status: SpawnStatus) -> None:
    """Raise ValueError if the transition is not allowed."""
    allowed = _ALLOWED_TRANSITIONS.get(from_status, frozenset())
    if to_status not in allowed:
        raise ValueError(
            f"Invalid spawn transition: {from_status!r} → {to_status!r}. "
            f"Allowed from {from_status!r}: {sorted(allowed)}"
        )
```

### Integration with spawn_store

```python
# src/meridian/lib/state/spawn_store.py

from meridian.lib.core.spawn_lifecycle import validate_transition, is_active, is_terminal

def mark_spawn_running(state_root: Path, spawn_id: str, *, launch_mode: str, ...) -> None:
    """Transition a spawn from queued to running."""
    record = get_spawn(state_root, spawn_id)
    if record is not None:
        validate_transition(record.status, "running")
    # ... existing update logic ...

def finalize_spawn(state_root: Path, spawn_id: str, *, status: SpawnStatus, ...) -> None:
    """Transition a spawn to a terminal state."""
    validate_transition("running", status)  # Only running → terminal is normal.
    # ... existing finalize logic ...

def finalize_spawn_if_active(state_root: Path, spawn_id: str, *, status: SpawnStatus, ...) -> SpawnRecord | None:
    """Finalize only if currently active. Used by cancel and reaper."""
    record = get_spawn(state_root, spawn_id)
    if record is None or is_terminal(record.status):
        return record
    validate_transition(record.status, status)
    # ... existing logic ...
```

### Replace hardcoded string comparisons

Create additional predicates so callers never compare strings directly:

```python
# spawn_lifecycle.py

def is_succeeded(status: SpawnStatus) -> bool:
    return status == "succeeded"

def is_failed(status: SpawnStatus) -> bool:
    return status == "failed"

def is_cancelled(status: SpawnStatus) -> bool:
    return status == "cancelled"

def is_queued(status: SpawnStatus) -> bool:
    return status == "queued"

def is_running(status: SpawnStatus) -> bool:
    return status == "running"

def is_failed_or_cancelled(status: SpawnStatus) -> bool:
    return status in {"failed", "cancelled"}
```

**Migration examples:**

```python
# Before (reaper.py):
if record.status == "queued":

# After:
from meridian.lib.core.spawn_lifecycle import is_queued
if is_queued(record.status):

# Before (api.py):
if row.status == "failed":

# After:
from meridian.lib.core.spawn_lifecycle import is_failed
if is_failed(row.status):

# Before (spawn_store.py):
None if event.status == "succeeded" else ...

# After:
None if is_succeeded(event.status) else ...
```

### Eliminate duplicate stats aggregation

**Problem (from consistency review):** `spawn_store.spawn_stats()` and `spawn_stats_sync()` in `api.py` both aggregate spawn statistics with different output shapes.

**Fix:** Keep one authoritative aggregation in the state layer, shape output in the ops layer.

```python
# spawn_store.py -- single source of truth
def spawn_stats(state_root: Path) -> dict[SpawnStatus, int]:
    """Count spawns by status."""
    records = list_spawns(state_root)
    counts: dict[SpawnStatus, int] = {}
    for r in records:
        counts[r.status] = counts.get(r.status, 0) + 1
    return counts

# api.py -- shapes for CLI/MCP output
def spawn_stats_sync(payload, ctx=None) -> SpawnStatsOutput:
    counts = spawn_store.spawn_stats(state_root)
    return SpawnStatsOutput(
        total=sum(counts.values()),
        succeeded=counts.get("succeeded", 0),
        failed=counts.get("failed", 0),
        cancelled=counts.get("cancelled", 0),
        running=counts.get("running", 0),
        queued=counts.get("queued", 0),
        by_status=counts,
    )
```

### Impact

- All state transitions validated at the boundary -- invalid transitions fail fast
- New states (e.g., `retrying`) require one edit to `_ALLOWED_TRANSITIONS` + predicates
- No more string literals for status checks scattered across the codebase
- Stats aggregation defined once, shaped at the output layer

---

## Phase 12: Stale Detection & Reused Chat IDs

Two smaller fixes that depend on the cleaner abstractions from earlier phases.

### 12a. Configurable stale threshold with heartbeat support

**Problem:** The reaper marks spawns as stale after 5 minutes of no output. Any harness that buffers output or spends more than 5 minutes in a quiet tool call gets killed while healthy.

**Solution:** Two changes:

1. **Make the threshold configurable** via project config:
```python
# Default in reaper.py
_DEFAULT_STALE_THRESHOLD_SECS = 300  # 5 minutes

def _get_stale_threshold(state_root: Path) -> int:
    """Read stale threshold from config, falling back to default."""
    # Reads from .meridian/config.json "stale_threshold_secs" key.
    config = _read_config(state_root)
    return config.get("stale_threshold_secs", _DEFAULT_STALE_THRESHOLD_SECS)
```

2. **Add a heartbeat file** that harnesses can touch to signal liveness without producing output:

```python
# reaper.py -- check heartbeat in staleness detection
_HEARTBEAT_FILENAME = "heartbeat"

def _spawn_is_stale(spawn_dir: Path, pid_file: Path, *, threshold: int) -> bool:
    now = time.time()

    # Check output activity.
    for name in ("output.jsonl", "stderr.log", _HEARTBEAT_FILENAME):
        path = spawn_dir / name
        try:
            if now - path.stat().st_mtime < threshold:
                return False
        except OSError:
            continue

    # Fall back to PID file age as proxy for spawn start time.
    try:
        if now - pid_file.stat().st_mtime < threshold:
            return False
    except OSError:
        pass

    return True
```

The runner can touch the heartbeat file periodically during long operations:

```python
# runner.py -- touch heartbeat every 60s during execution
async def _heartbeat_loop(spawn_dir: Path, interval: float = 60.0):
    heartbeat_path = spawn_dir / "heartbeat"
    while True:
        await asyncio.sleep(interval)
        heartbeat_path.touch()
```

This is non-invasive: harnesses that don't touch the heartbeat file get the same behavior as before (stale after threshold). Harnesses that do touch it extend their liveness window.

### 12b. Fix `collect_active_chat_ids()` for reused chat IDs

**Problem:** The function uses set subtraction (`started - stopped`), which ignores event ordering. The sequence `start(c7)`, `stop(c7)`, `start(c7)` yields `started={"c7"}`, `stopped={"c7"}`, result = empty set -- but `c7` is active.

**Fix:** Process events in order, tracking the latest state per chat ID:

```python
def collect_active_chat_ids(repo_root: Path) -> frozenset[str]:
    """Return chat IDs with currently-active sessions.

    Processes events in order so reused chat IDs are handled correctly.
    """
    state_root = resolve_state_paths(resolve_repo_root(repo_root)).root_dir
    sessions_file = state_root / "sessions.jsonl"

    try:
        events = read_events(sessions_file, _parse_event)
    except OSError:
        return frozenset()

    # Track latest state per chat_id. Last event wins.
    latest: dict[str, str] = {}  # chat_id -> "start" | "stop"
    for event in events:
        if isinstance(event, SessionStartEvent):
            latest[event.chat_id] = "start"
        elif isinstance(event, SessionStopEvent):
            latest[event.chat_id] = "stop"

    return frozenset(
        chat_id for chat_id, state in latest.items() if state == "start"
    )
```

This is a one-for-one replacement. The event log is already ordered (append-only JSONL), so processing in file order gives the correct latest state.

---

## Updated Implementation Sequence

```
Phase 1   Dead code & quick fixes ──────────────────────────>  commit
    │
Phase 2   Shared JSONL event store ──────────────────────────>  commit
    │
Phase 3   Unified error semantics ──────>  commit
    │
Phase 4   Ops helpers ──────>  commit       Phase 5   Async wrappers ──────>  commit
    │                                            │
Phase 6   Session lifecycle extraction ──────────────────────>  commit
    │
Phase 7   Harness adapter ISP ──────────────────────────────>  commit
    │
Phase 8   CLI registration ──────>  commit
    │
Phase 9   Session lock-order fix ──────>  commit
    │
Phase 10  PID-before-fork & launch mutex ───────────────────>  commit
    │
Phase 11  Spawn state machine ──────────────────────────────>  commit
    │
Phase 12  Stale detection & reused chat IDs ──────>  commit
```

Phases 9-12 build on the cleaner abstractions from 1-8:
- Phase 9 uses `lock_file` from Phase 2's shared event store.
- Phase 10 integrates with Phase 6's `SessionScope` for the primary launch path.
- Phase 11 replaces the `ACTIVE_SPAWN_STATUSES` checks that Phase 2's shared store uses.
- Phase 12 uses `read_events` from Phase 2 for the chat ID fix.
