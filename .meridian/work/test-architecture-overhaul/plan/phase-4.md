# Phase 4: Process Module Split

## Objective
Split process.py into ProcessLauncher protocol with PTY and Subprocess implementations.

## Commits (Execute in Order)

### Commit 4.1: Create lib/launch/process/ports.py
Create directory structure:
```
src/meridian/lib/launch/process/
├── __init__.py       # Re-exports
└── ports.py          # ProcessLauncher protocol
```

`ports.py`:
```python
"""Process launcher protocols."""
from typing import Protocol
from dataclasses import dataclass

@dataclass(frozen=True)
class LaunchedProcess:
    """Handle to a launched process."""
    pid: int
    # Add other necessary fields

class ProcessLauncher(Protocol):
    """Protocol for process launching strategies."""
    def launch(self, cmd: list[str], env: dict[str, str], **kwargs) -> LaunchedProcess: ...
```

Validation: Import works

### Commit 4.2: Create pty_launcher.py
Create `src/meridian/lib/launch/process/pty_launcher.py`:
- Extract PTY-specific logic from process.py
- Implement ProcessLauncher protocol

Validation: Import works

### Commit 4.3: Create subprocess_launcher.py
Create `src/meridian/lib/launch/process/subprocess_launcher.py`:
- Extract subprocess-specific logic from process.py
- Implement ProcessLauncher protocol as fallback

Validation: Import works

### Commit 4.4: Extract Session Logic
Create `src/meridian/lib/launch/process/session.py`:
- Extract session bookkeeping from process.py
- Session start/stop, metadata tracking

Validation: Import works

### Commit 4.5: Create Slim runner.py
Create `src/meridian/lib/launch/process/runner.py`:
- Thin orchestration layer composing launchers + session
- Main entry point for process execution

Validation: Existing tests pass

### Commit 4.6: Update Original process.py for Backward Compat
Update `src/meridian/lib/launch/process.py`:
- Re-export from new locations
- Keep public API intact
- Existing imports continue working

Validation: Existing tests pass

## Files to Touch
- Create: `src/meridian/lib/launch/process/__init__.py`
- Create: `src/meridian/lib/launch/process/ports.py`
- Create: `src/meridian/lib/launch/process/pty_launcher.py`
- Create: `src/meridian/lib/launch/process/subprocess_launcher.py`
- Create: `src/meridian/lib/launch/process/session.py`
- Create: `src/meridian/lib/launch/process/runner.py`
- Modify: `src/meridian/lib/launch/process.py` (backward compat re-exports)

## Exit Criteria
- All 6 commits made atomically
- Each commit passes pytest
- ProcessLauncher protocol available
- PTY and Subprocess implementations available
- Original process.py imports still work
