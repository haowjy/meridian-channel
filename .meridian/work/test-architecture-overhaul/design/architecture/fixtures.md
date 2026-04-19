# Test Fixtures — Technical Architecture

## Design Principles

1. **Explicit imports** — All fixtures come from `tests/support/` or directory conftest.py, never implicit cross-conftest imports
2. **Factory over instance** — Fixtures that create multiple instances use factory pattern
3. **Yield for cleanup** — Fixtures with cleanup use `yield`, not separate teardown
4. **Function scope default** — Use broader scope only with explicit justification

---

## Fake Implementations

### tests/support/fakes.py

```python
"""Fake implementations of production protocols for unit testing.

All fakes match their protocol exactly — they're validated by contract tests.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from meridian.lib.core.types import SpawnId


# ── FakeClock ───────────────────────────────────────────────────────────────


@dataclass
class FakeClock:
    """Injectable clock for deterministic time in tests.
    
    Usage:
        clock = FakeClock(start=1000.0)
        assert clock.monotonic() == 1000.0
        clock.advance(5.0)
        assert clock.monotonic() == 1005.0
    """
    _now: float = 0.0
    _time_offset: float = 0.0  # Difference between time() and monotonic()
    
    def __init__(self, start: float = 0.0, time_offset: float = 1_700_000_000.0) -> None:
        self._now = start
        self._time_offset = time_offset
    
    def monotonic(self) -> float:
        """Return fake monotonic time."""
        return self._now
    
    def time(self) -> float:
        """Return fake epoch time (monotonic + offset)."""
        return self._now + self._time_offset
    
    def utc_now_iso(self) -> str:
        """Return fake ISO timestamp."""
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(self.time(), tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    
    def advance(self, seconds: float) -> None:
        """Advance time by seconds."""
        self._now += seconds
    
    def set(self, value: float) -> None:
        """Set absolute monotonic time."""
        self._now = value


# ── FakeFileAdapter ─────────────────────────────────────────────────────────


@dataclass
class FakeFileAdapter:
    """In-memory file adapter for unit tests.
    
    Usage:
        adapter = FakeFileAdapter()
        adapter.append_line(Path("test.txt"), "line1")
        assert adapter.read_lines(Path("test.txt")) == ["line1"]
    """
    _files: dict[Path, list[str]] = field(default_factory=dict)
    
    def read_lines(self, path: Path) -> list[str]:
        """Read lines from in-memory file."""
        return list(self._files.get(path, []))
    
    def append_line(self, path: Path, line: str) -> None:
        """Append line to in-memory file."""
        if path not in self._files:
            self._files[path] = []
        clean_line = line.rstrip("\n")
        self._files[path].append(clean_line)
    
    def exists(self, path: Path) -> bool:
        """Check if in-memory file exists."""
        return path in self._files
    
    def clear(self) -> None:
        """Clear all files (for test reset)."""
        self._files.clear()


# ── FakeLockAdapter ─────────────────────────────────────────────────────────


@dataclass
class FakeLockAdapter:
    """No-op lock adapter for unit tests.
    
    Records lock/unlock calls for verification.
    """
    lock_calls: list[Path] = field(default_factory=list)
    unlock_calls: list[Path] = field(default_factory=list)
    
    @contextmanager
    def lock(self, path: Path) -> Iterator[None]:
        """No-op lock that records calls."""
        self.lock_calls.append(path)
        try:
            yield
        finally:
            self.unlock_calls.append(path)


# ── FakeHeartbeatAdapter ────────────────────────────────────────────────────


@dataclass
class FakeHeartbeatAdapter:
    """Records heartbeat touches for verification.
    
    Usage:
        adapter = FakeHeartbeatAdapter()
        adapter.touch(state_root, spawn_id)
        assert len(adapter.touches) == 1
    """
    touches: list[tuple[Path, SpawnId]] = field(default_factory=list)
    
    def touch(self, state_root: Path, spawn_id: SpawnId) -> None:
        """Record touch call."""
        self.touches.append((state_root, spawn_id))
    
    def clear(self) -> None:
        """Clear recorded touches."""
        self.touches.clear()


# ── FakeSpawnStoreAdapter ───────────────────────────────────────────────────


@dataclass
class FakeSpawnStoreAdapter:
    """In-memory spawn store for unit tests.
    
    Records all operations for verification.
    """
    spawns: dict[str, dict] = field(default_factory=dict)
    update_calls: list[tuple[str, dict]] = field(default_factory=list)
    finalize_calls: list[tuple[str, dict]] = field(default_factory=list)
    
    def update_spawn(
        self,
        state_root: Path,
        spawn_id: SpawnId,
        **kwargs,
    ) -> None:
        """Record update call and merge into spawn dict."""
        sid = str(spawn_id)
        self.update_calls.append((sid, kwargs))
        if sid not in self.spawns:
            self.spawns[sid] = {}
        self.spawns[sid].update(kwargs)
    
    def mark_finalizing(self, state_root: Path, spawn_id: SpawnId) -> bool:
        """Mark spawn as finalizing, return success."""
        sid = str(spawn_id)
        if sid not in self.spawns:
            return False
        current = self.spawns[sid].get("status", "running")
        if current != "running":
            return False
        self.spawns[sid]["status"] = "finalizing"
        return True
    
    def finalize_spawn(
        self,
        state_root: Path,
        spawn_id: SpawnId,
        status: str,
        exit_code: int,
        origin: str,
        **kwargs,
    ) -> bool:
        """Record finalize and update spawn status."""
        sid = str(spawn_id)
        self.finalize_calls.append((sid, {"status": status, "exit_code": exit_code, "origin": origin, **kwargs}))
        was_active = self.spawns.get(sid, {}).get("status") in ("queued", "running", "finalizing")
        if sid not in self.spawns:
            self.spawns[sid] = {}
        self.spawns[sid].update(status=status, exit_code=exit_code)
        return was_active
    
    def record_spawn_exited(
        self,
        state_root: Path,
        spawn_id: SpawnId,
        exit_code: int,
    ) -> None:
        """Record process exit."""
        sid = str(spawn_id)
        if sid not in self.spawns:
            self.spawns[sid] = {}
        self.spawns[sid]["process_exit_code"] = exit_code
    
    def get_spawn(self, state_root: Path, spawn_id: SpawnId):
        """Return spawn dict or None."""
        return self.spawns.get(str(spawn_id))


# ── FakeSubprocess ──────────────────────────────────────────────────────────


@dataclass
class FakeSubprocess:
    """Fake subprocess runner for unit tests.
    
    Usage:
        fake = FakeSubprocess(results={
            ("echo", "hello"): (0, "hello\\n", ""),
            ("false",): (1, "", ""),
        })
        exit_code, stdout, stderr = fake.run(("echo", "hello"))
        assert exit_code == 0
    """
    results: dict[tuple[str, ...], tuple[int, str, str]] = field(default_factory=dict)
    calls: list[tuple[str, ...]] = field(default_factory=list)
    
    def run(
        self,
        command: tuple[str, ...],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> tuple[int, str, str]:
        """Return pre-configured result for command."""
        self.calls.append(command)
        if command in self.results:
            return self.results[command]
        # Default: command not found
        return (127, "", f"command not found: {command[0]}")


# ── FakeProcessLauncher ─────────────────────────────────────────────────────


@dataclass  
class FakeProcessLauncher:
    """Fake process launcher for unit tests.
    
    Allows testing process lifecycle without real subprocess.
    """
    results: dict[tuple[str, ...], tuple[int, int]] = field(default_factory=dict)  # (exit_code, pid)
    launches: list[tuple[tuple[str, ...], Path, dict]] = field(default_factory=list)
    _next_pid: int = 1000
    
    @staticmethod
    def is_available() -> bool:
        return True
    
    def launch(
        self,
        command: tuple[str, ...],
        cwd: Path,
        env: dict[str, str],
        output_log_path: Path | None,
        on_started=None,
    ) -> tuple[int, int | None]:
        """Return pre-configured result for command."""
        self.launches.append((command, cwd, env))
        
        if command in self.results:
            exit_code, pid = self.results[command]
        else:
            exit_code, pid = 0, self._next_pid
            self._next_pid += 1
        
        if on_started is not None:
            on_started(pid)
        
        return exit_code, pid


# ── FakePlatformDetector ────────────────────────────────────────────────────


@dataclass
class FakePlatformDetector:
    """Injectable platform detector for testing platform-specific logic."""
    _is_windows: bool = False
    _is_posix: bool = True
    _tty_fds: set[int] = field(default_factory=set)
    
    @property
    def is_windows(self) -> bool:
        return self._is_windows
    
    @property
    def is_posix(self) -> bool:
        return self._is_posix
    
    def is_tty(self, fd: int) -> bool:
        return fd in self._tty_fds
    
    @classmethod
    def windows(cls) -> FakePlatformDetector:
        """Create Windows-simulating detector."""
        return cls(_is_windows=True, _is_posix=False)
    
    @classmethod
    def posix_with_tty(cls) -> FakePlatformDetector:
        """Create POSIX detector with stdin/stdout as TTY."""
        return cls(_is_windows=False, _is_posix=True, _tty_fds={0, 1, 2})
```

---

## Factory Fixtures

### tests/support/fixtures.py

```python
"""Factory fixtures for test state creation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from meridian.lib.core.types import SpawnId


@dataclass
class StateRootFactory:
    """Creates isolated state roots for testing."""
    _base: Path
    _counter: int = 0
    
    def create(self, name: str | None = None) -> Path:
        """Create new isolated state root."""
        self._counter += 1
        dirname = name or f"state_{self._counter}"
        root = self._base / dirname / ".meridian"
        root.mkdir(parents=True, exist_ok=True)
        (root / "spawns").mkdir(exist_ok=True)
        (root / "sessions").mkdir(exist_ok=True)
        (root / "artifacts").mkdir(exist_ok=True)
        return root


def make_state_root_factory(tmp_path: Path) -> StateRootFactory:
    """Create state root factory for tmp_path session."""
    return StateRootFactory(_base=tmp_path)


@dataclass
class SpawnRecordBuilder:
    """Builder for test spawn records."""
    _id: str = "p1"
    _chat_id: str = "test-chat"
    _model: str = "test-model"
    _agent: str = "test-agent"
    _status: str = "running"
    
    def with_id(self, id: str) -> SpawnRecordBuilder:
        self._id = id
        return self
    
    def with_status(self, status: str) -> SpawnRecordBuilder:
        self._status = status
        return self
    
    def build(self):
        """Build SpawnRecord with configured values."""
        from meridian.lib.state.spawn.events import SpawnRecord
        return SpawnRecord(
            id=self._id,
            chat_id=self._chat_id,
            parent_id=None,
            model=self._model,
            agent=self._agent,
            agent_path=None,
            skills=(),
            skill_paths=(),
            harness="test",
            kind="child",
            desc=None,
            work_id=None,
            harness_session_id=None,
            execution_cwd=None,
            launch_mode="foreground",
            worker_pid=None,
            runner_pid=None,
            status=self._status,
            prompt="test prompt",
            started_at=None,
            exited_at=None,
            process_exit_code=None,
            finished_at=None,
            exit_code=None,
            duration_secs=None,
            total_cost_usd=None,
            input_tokens=None,
            output_tokens=None,
            error=None,
            terminal_origin=None,
        )


def spawn_record_builder() -> SpawnRecordBuilder:
    """Create new spawn record builder."""
    return SpawnRecordBuilder()
```

---

## Conftest Fixtures

### tests/conftest.py (root)

```python
"""Root conftest: global fixtures and marker registration."""

import os
import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only test")
windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: pure logic tests, no I/O")
    config.addinivalue_line("markers", "integration: one real boundary")
    config.addinivalue_line("markers", "e2e: full CLI invocation")
    config.addinivalue_line("markers", "contract: parity/drift checks")
    config.addinivalue_line("markers", "posix_only: test requires POSIX semantics")
    config.addinivalue_line("markers", "windows_only: test requires Windows semantics")
    config.addinivalue_line("markers", "slow: takes longer than 1 second")


@pytest.fixture
def package_root() -> Path:
    return PACKAGE_ROOT


@pytest.fixture(autouse=True)
def _clean_meridian_runtime_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate tests from parent harness runtime state environment."""
    for key in tuple(os.environ):
        if key.startswith("MERIDIAN_"):
            monkeypatch.delenv(key, raising=False)
```

### tests/unit/conftest.py

```python
"""Unit test conftest: auto-marker and unit-specific fixtures."""

import pytest

from tests.support.fakes import (
    FakeClock,
    FakeFileAdapter,
    FakeHeartbeatAdapter,
    FakeLockAdapter,
    FakeSpawnStoreAdapter,
)


def pytest_collection_modifyitems(items):
    """Auto-apply @pytest.mark.unit to tests in unit/ directory."""
    for item in items:
        if "/unit/" in str(item.fspath):
            item.add_marker(pytest.mark.unit)


@pytest.fixture
def fake_clock() -> FakeClock:
    """Provide fresh FakeClock for test."""
    return FakeClock()


@pytest.fixture
def fake_file_adapter() -> FakeFileAdapter:
    """Provide fresh FakeFileAdapter for test."""
    return FakeFileAdapter()


@pytest.fixture
def fake_lock_adapter() -> FakeLockAdapter:
    """Provide fresh FakeLockAdapter for test."""
    return FakeLockAdapter()


@pytest.fixture
def fake_heartbeat_adapter() -> FakeHeartbeatAdapter:
    """Provide fresh FakeHeartbeatAdapter for test."""
    return FakeHeartbeatAdapter()


@pytest.fixture
def fake_spawn_store() -> FakeSpawnStoreAdapter:
    """Provide fresh FakeSpawnStoreAdapter for test."""
    return FakeSpawnStoreAdapter()
```

### tests/integration/conftest.py

```python
"""Integration test conftest: auto-marker and integration fixtures."""

import pytest

from tests.support.fixtures import make_state_root_factory


def pytest_collection_modifyitems(items):
    """Auto-apply @pytest.mark.integration to tests in integration/ directory."""
    for item in items:
        if "/integration/" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


@pytest.fixture
def state_root_factory(tmp_path):
    """Factory for creating isolated state roots."""
    return make_state_root_factory(tmp_path)


@pytest.fixture
def state_root(state_root_factory):
    """Single isolated state root for simple tests."""
    return state_root_factory.create()
```

---

## Contract Tests

### tests/contract/test_clock_protocol.py

```python
"""Contract tests verifying all Clock implementations match protocol."""

import pytest

from meridian.lib.core.clock import RealClock
from tests.support.fakes import FakeClock


@pytest.mark.contract
class TestClockProtocol:
    """All Clock implementations must pass these tests."""
    
    @pytest.fixture(params=["real", "fake"])
    def clock(self, request):
        if request.param == "real":
            return RealClock()
        return FakeClock()
    
    def test_monotonic_returns_float(self, clock):
        result = clock.monotonic()
        assert isinstance(result, float)
    
    def test_time_returns_float(self, clock):
        result = clock.time()
        assert isinstance(result, float)
    
    def test_monotonic_is_non_decreasing(self, clock):
        t1 = clock.monotonic()
        t2 = clock.monotonic()
        assert t2 >= t1
    
    def test_utc_now_iso_returns_string(self, clock):
        result = clock.utc_now_iso()
        assert isinstance(result, str)
        assert "T" in result  # ISO format
```

---

## Usage Example

```python
# tests/unit/launch/test_heartbeat.py

from tests.support.fakes import FakeClock, FakeHeartbeatAdapter
from meridian.lib.launch.streaming.heartbeat import HeartbeatManager


async def test_heartbeat_touches_at_interval():
    """Heartbeat manager touches file at configured interval."""
    clock = FakeClock(start=0.0)
    heartbeat = FakeHeartbeatAdapter()
    
    manager = HeartbeatManager(
        state_root=Path("/fake"),
        interval_secs=10.0,
        clock=clock,
        heartbeat_adapter=heartbeat,
    )
    
    await manager.start(SpawnId("p1"))
    
    # Simulate time passing
    clock.advance(10.0)
    await asyncio.sleep(0)  # Let event loop process
    
    assert len(heartbeat.touches) >= 1
    
    await manager.stop()
```
