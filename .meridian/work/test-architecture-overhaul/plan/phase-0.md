# Phase 0: Foundation

## Objective
Set up foundational infrastructure for the test architecture overhaul: Clock protocol, tests/support/ structure, marker registration, and centralized Unix module proxy.

## Commits (Execute in Order)

### Commit 0.1: Create Clock Protocol
Create `src/meridian/lib/core/clock.py`:
```python
"""Shared time abstraction for dependency injection."""
from datetime import datetime, timezone
import time
from typing import Protocol

class Clock(Protocol):
    def monotonic(self) -> float: ...
    def time(self) -> float: ...
    def utc_now_iso(self) -> str: ...

class RealClock:
    def monotonic(self) -> float:
        return time.monotonic()
    def time(self) -> float:
        return time.time()
    def utc_now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
```

Validation: Import works

### Commit 0.2: Create tests/support/
Create directory structure:
```
tests/support/
├── __init__.py       # Empty or re-exports
├── fakes.py          # FakeClock implementation
├── fixtures.py       # Empty placeholder
└── assertions.py     # Empty placeholder
```

FakeClock in fakes.py:
```python
from datetime import datetime, timezone

class FakeClock:
    def __init__(self, start: float = 0.0):
        self._now = start
    def monotonic(self) -> float:
        return self._now
    def time(self) -> float:
        return self._now
    def utc_now_iso(self) -> str:
        return datetime.fromtimestamp(self._now, tz=timezone.utc).isoformat()
    def advance(self, seconds: float) -> None:
        self._now += seconds
```

Validation: `from tests.support.fakes import FakeClock` works

### Commit 0.3: Add Marker Registration
Update `tests/conftest.py` to add markers:
```python
def pytest_configure(config):
    # existing markers...
    config.addinivalue_line("markers", "unit: pure logic tests, no IO")
    config.addinivalue_line("markers", "integration: one real boundary")
    config.addinivalue_line("markers", "e2e: full CLI invocation")
    config.addinivalue_line("markers", "contract: parity/drift checks")
    config.addinivalue_line("markers", "slow: takes >1s")
```

Validation: `pytest --markers` shows new markers

### Commit 0.4: Centralize Unix Module Proxy
Create `src/meridian/lib/platform/unix_modules.py`:
```python
"""Lazy Unix module proxies for cross-platform compatibility."""
from importlib import import_module
from typing import Any

class DeferredUnixModule:
    """Lazy module proxy so Unix-only modules load only on demand."""
    def __init__(self, module_name: str) -> None:
        self._module_name = module_name
        self._module: Any | None = None

    def _resolve(self) -> Any:
        if self._module is None:
            self._module = import_module(self._module_name)
        return self._module

    def __getattr__(self, name: str) -> Any:
        return getattr(self._resolve(), name)

fcntl = DeferredUnixModule("fcntl")
termios = DeferredUnixModule("termios")
```

Update `src/meridian/lib/platform/__init__.py` to export:
```python
from .unix_modules import DeferredUnixModule, fcntl, termios
```

Validation: Import works, existing tests pass

### Commit 0.5: Update process.py
Update `src/meridian/lib/launch/process.py`:
- Remove local `_DeferredUnixModule` class (lines 49-62)
- Remove local `fcntl = _DeferredUnixModule("fcntl")` and `termios = ...`
- Add import: `from meridian.lib.platform import fcntl, termios`

Validation: Existing tests pass

### Commit 0.6: Update session_store.py
Update `src/meridian/lib/state/session_store.py`:
- Remove local `_DeferredUnixModule` class (lines 21-34)
- Remove local `fcntl = _DeferredUnixModule("fcntl")`
- Add import: `from meridian.lib.platform import fcntl`

Validation: Existing tests pass

## Exit Criteria
- All 6 commits made atomically
- Each commit passes `pytest` (run full suite)
- Imports from new locations work
- No regressions
