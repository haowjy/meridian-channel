# Streaming Runner — Technical Architecture

## Current State

`streaming_runner.py` is 1244 lines containing:
- `terminal_event_outcome()` — Pure harness event classification
- `_touch_heartbeat_file()` — Direct filesystem access
- `_HEARTBEAT_INTERVAL_SECS` — Module constant that tests monkeypatch
- `_install_signal_handlers()` / `_remove_signal_handlers()` — Signal setup
- `_run_streaming_attempt()` — 234-line async function mixing everything
- `execute_with_streaming()` — 493-line main entry point

Tests currently monkeypatch `_HEARTBEAT_INTERVAL_SECS` and `_touch_heartbeat_file` to control timing and filesystem access.

---

## Target State

```
src/meridian/lib/launch/streaming/
├── __init__.py          # Re-exports for public API
├── adapters.py          # Protocol definitions + real implementations
├── decision.py          # Pure decision logic (retry, terminal, classify)
├── heartbeat.py         # HeartbeatManager with injectable clock/touch
└── runner.py            # Thin orchestration shell
```

---

## File Details

### adapters.py

```python
"""Protocol definitions for streaming runner dependencies."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterator
    from meridian.lib.core.types import SpawnId

# Import shared Clock from core
from meridian.lib.core.clock import Clock  # noqa: F401


class HeartbeatAdapter(Protocol):
    """Injectable heartbeat file operations."""
    
    def touch(self, state_root: Path, spawn_id: SpawnId) -> None:
        """Touch heartbeat file to signal liveness."""
        ...


class SpawnStoreAdapter(Protocol):
    """Injectable spawn-store operations for runner."""
    
    def update_spawn(
        self,
        state_root: Path,
        spawn_id: SpawnId,
        **kwargs,
    ) -> None: ...
    
    def mark_finalizing(self, state_root: Path, spawn_id: SpawnId) -> bool: ...
    
    def finalize_spawn(
        self,
        state_root: Path,
        spawn_id: SpawnId,
        status: str,
        exit_code: int,
        origin: str,
        **kwargs,
    ) -> bool: ...
    
    def record_spawn_exited(
        self,
        state_root: Path,
        spawn_id: SpawnId,
        exit_code: int,
    ) -> None: ...
    
    def get_spawn(self, state_root: Path, spawn_id: SpawnId): ...


class SignalCoordinatorAdapter(Protocol):
    """Injectable signal coordination for SIGTERM masking."""
    
    @contextmanager
    def mask_sigterm(self) -> Iterator[None]: ...


# ── Production Implementations ──────────────────────────────────────────────


class RealHeartbeatAdapter:
    """Production heartbeat implementation using real filesystem."""
    
    def touch(self, state_root: Path, spawn_id: SpawnId) -> None:
        from meridian.lib.state import paths as state_paths
        heartbeat_path = state_paths.heartbeat_path(state_root, spawn_id)
        heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
        heartbeat_path.touch(exist_ok=True)


class RealSpawnStoreAdapter:
    """Production spawn-store implementation delegating to spawn_store module."""
    
    def update_spawn(self, state_root: Path, spawn_id: SpawnId, **kwargs) -> None:
        from meridian.lib.state import spawn_store
        spawn_store.update_spawn(state_root, spawn_id, **kwargs)
    
    def mark_finalizing(self, state_root: Path, spawn_id: SpawnId) -> bool:
        from meridian.lib.state import spawn_store
        return spawn_store.mark_finalizing(state_root, spawn_id)
    
    def finalize_spawn(
        self,
        state_root: Path,
        spawn_id: SpawnId,
        status: str,
        exit_code: int,
        origin: str,
        **kwargs,
    ) -> bool:
        from meridian.lib.state import spawn_store
        return spawn_store.finalize_spawn(
            state_root, spawn_id,
            status=status, exit_code=exit_code, origin=origin,
            **kwargs,
        )
    
    def record_spawn_exited(
        self,
        state_root: Path,
        spawn_id: SpawnId,
        exit_code: int,
    ) -> None:
        from meridian.lib.state import spawn_store
        spawn_store.record_spawn_exited(state_root, spawn_id, exit_code=exit_code)
    
    def get_spawn(self, state_root: Path, spawn_id: SpawnId):
        from meridian.lib.state import spawn_store
        return spawn_store.get_spawn(state_root, spawn_id)


class RealSignalCoordinator:
    """Production signal coordinator delegating to signals module."""
    
    @contextmanager
    def mask_sigterm(self) -> Iterator[None]:
        from meridian.lib.launch.signals import signal_coordinator
        with signal_coordinator().mask_sigterm():
            yield
```

### decision.py

```python
"""Pure decision logic for streaming runner — no I/O, no async."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from meridian.lib.harness.connections.base import HarnessEvent

from meridian.lib.core.types import HarnessId
from meridian.lib.core.domain import SpawnStatus


@dataclass(frozen=True)
class TerminalEventOutcome:
    """Result of classifying a terminal harness event."""
    status: SpawnStatus
    exit_code: int
    error: str | None = None


def terminal_event_outcome(event: HarnessEvent) -> TerminalEventOutcome | None:
    """Classify a harness event as terminal or non-terminal.
    
    Pure function: operates only on event data, no I/O.
    Returns TerminalEventOutcome if event is terminal, None otherwise.
    """
    # Claude Code result event
    if event.harness_id == HarnessId.CLAUDE.value and event.event_type == "result":
        # ... (existing logic moved here)
        pass
    
    # Codex turn/completed
    if event.harness_id == HarnessId.CODEX.value and event.event_type == "turn/completed":
        return TerminalEventOutcome(status="succeeded", exit_code=0)
    
    # OpenCode session.idle / session.error
    if event.harness_id == HarnessId.OPENCODE.value:
        if event.event_type == "session.idle":
            return TerminalEventOutcome(status="succeeded", exit_code=0)
        if event.event_type == "session.error":
            # ... (existing logic)
            pass
    
    # Connection closed
    if event.event_type == "error/connectionClosed":
        return TerminalEventOutcome(status="failed", exit_code=1, error="connection_closed")
    
    return None


# ── Retry Decision Logic ──────────────────────────────────────────────────

# Move existing should_retry(), classify_error() from errors.py here
# These are already pure functions, just need relocation
```

### heartbeat.py

```python
"""Heartbeat management with injectable clock and touch function."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from meridian.lib.core.types import SpawnId
    from meridian.lib.core.clock import Clock
    from .adapters import HeartbeatAdapter


class HeartbeatManager:
    """Manages periodic heartbeat file touches with injectable dependencies."""
    
    def __init__(
        self,
        *,
        state_root: Path,
        interval_secs: float,
        clock: Clock,
        heartbeat_adapter: HeartbeatAdapter,
    ) -> None:
        self._state_root = state_root
        self._interval_secs = interval_secs
        self._clock = clock
        self._heartbeat_adapter = heartbeat_adapter
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
    
    async def start(self, spawn_id: SpawnId) -> None:
        """Start periodic heartbeat touches for spawn."""
        self._stop_event.clear()
        self._task = asyncio.create_task(self._heartbeat_loop(spawn_id))
    
    async def stop(self) -> None:
        """Stop heartbeat loop gracefully."""
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
    
    async def _heartbeat_loop(self, spawn_id: SpawnId) -> None:
        """Periodic heartbeat touch loop."""
        while not self._stop_event.is_set():
            self._heartbeat_adapter.touch(self._state_root, spawn_id)
            try:
                await asyncio.sleep(self._interval_secs)
            except asyncio.CancelledError:
                break
    
    def touch_once(self, spawn_id: SpawnId) -> None:
        """Synchronous single heartbeat touch."""
        self._heartbeat_adapter.touch(self._state_root, spawn_id)
```

### runner.py

```python
"""Thin orchestration shell composing decision, heartbeat, and adapters."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from .adapters import (
    HeartbeatAdapter,
    RealHeartbeatAdapter,
    RealSignalCoordinator,
    RealSpawnStoreAdapter,
    SignalCoordinatorAdapter,
    SpawnStoreAdapter,
)
from .decision import terminal_event_outcome, TerminalEventOutcome
from .heartbeat import HeartbeatManager
from meridian.lib.core.clock import Clock, RealClock

if TYPE_CHECKING:
    from meridian.lib.core.domain import Spawn
    from meridian.lib.launch.request import SpawnRequest
    # ... other imports


DEFAULT_HEARTBEAT_INTERVAL_SECS = 30.0


async def execute_with_streaming(
    run: Spawn,
    *,
    # ... existing parameters ...
    # NEW: injectable dependencies with production defaults
    clock: Clock | None = None,
    heartbeat_adapter: HeartbeatAdapter | None = None,
    spawn_store_adapter: SpawnStoreAdapter | None = None,
    signal_coordinator: SignalCoordinatorAdapter | None = None,
    heartbeat_interval_secs: float = DEFAULT_HEARTBEAT_INTERVAL_SECS,
) -> int:
    """Execute one streaming spawn with injectable dependencies.
    
    All dependencies default to production implementations if not provided.
    Tests inject fakes; production code calls with no optional args.
    """
    # Default to production implementations
    clock = clock or RealClock()
    heartbeat_adapter = heartbeat_adapter or RealHeartbeatAdapter()
    spawn_store_adapter = spawn_store_adapter or RealSpawnStoreAdapter()
    signal_coordinator = signal_coordinator or RealSignalCoordinator()
    
    heartbeat = HeartbeatManager(
        state_root=state_root,
        interval_secs=heartbeat_interval_secs,
        clock=clock,
        heartbeat_adapter=heartbeat_adapter,
    )
    
    # ... orchestration logic using injected dependencies ...
    # Replace direct spawn_store.* calls with spawn_store_adapter.*
    # Replace direct signal_coordinator() with signal_coordinator.mask_sigterm()
```

---

## Test Migration

### Before (current)
```python
def test_heartbeat_is_touched(monkeypatch, tmp_path, ...):
    touches = []
    def _tracked_touch(state_root, spawn_id):
        touches.append((state_root, spawn_id))
    
    monkeypatch.setattr(streaming_runner_module, "_HEARTBEAT_INTERVAL_SECS", 0.02)
    monkeypatch.setattr(streaming_runner_module, "_touch_heartbeat_file", _tracked_touch)
    
    # ... run test ...
```

### After (target)
```python
from tests.support.fakes import FakeClock, FakeHeartbeatAdapter

def test_heartbeat_is_touched(tmp_path, ...):
    fake_clock = FakeClock(start=0.0)
    fake_heartbeat = FakeHeartbeatAdapter()
    
    await execute_with_streaming(
        run=...,
        clock=fake_clock,
        heartbeat_adapter=fake_heartbeat,
        heartbeat_interval_secs=0.02,
    )
    
    assert len(fake_heartbeat.touches) > 0
```

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Large async function split breaks subtle timing | Keep decision.py pure; timing lives in runner.py |
| Protocol proliferation | Limit to 4 protocols; combine where natural |
| Performance overhead of adapters | Adapters are thin wrappers; measure if concerned |
| Backward compatibility break | Re-export from original path |
