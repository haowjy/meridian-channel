# Process Module — Technical Architecture

## Current State

`process.py` is 570 lines containing:
- `_DeferredUnixModule` — Lazy loader for Unix-only modules
- `_copy_primary_pty_output()` — PTY I/O loop with select/termios
- `_run_primary_process_with_capture()` — Fork/exec with PTY or fallback
- `_install_winsize_forwarding()` — SIGWINCH handling
- `run_harness_process()` — 279-line main entry mixing session + process + store

Tests currently need to run real fork/pty operations or skip on Windows.

---

## Target State

```
src/meridian/lib/launch/process/
├── __init__.py          # Re-exports for public API
├── ports.py             # ProcessLauncher protocol + platform detection
├── pty_launcher.py      # POSIX PTY implementation
├── subprocess_launcher.py # Cross-platform subprocess fallback
├── session.py           # Session management (extracted from run_harness_process)
└── runner.py            # Thin orchestration shell
```

---

## File Details

### ports.py

```python
"""Protocol definitions for process launching."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable


class ProcessLauncher(Protocol):
    """Injectable process launch mechanism."""
    
    def launch(
        self,
        command: tuple[str, ...],
        cwd: Path,
        env: dict[str, str],
        output_log_path: Path | None,
        on_started: Callable[[int], None] | None = None,
    ) -> tuple[int, int | None]:
        """Launch process and return (exit_code, child_pid).
        
        Args:
            command: Command and arguments to execute
            cwd: Working directory for child process
            env: Environment variables for child
            output_log_path: Path to log output (None = no capture)
            on_started: Callback with child PID once started
        
        Returns:
            Tuple of (exit_code, child_pid or None)
        """
        ...
    
    @staticmethod
    def is_available() -> bool:
        """Return True if this launcher works on current platform."""
        ...


class PlatformDetector(Protocol):
    """Injectable platform detection for testing."""
    
    @property
    def is_windows(self) -> bool: ...
    
    @property  
    def is_posix(self) -> bool: ...
    
    def is_tty(self, fd: int) -> bool: ...


# ── Production Implementation ──────────────────────────────────────────────


class RealPlatformDetector:
    """Production platform detection using sys and os."""
    
    @property
    def is_windows(self) -> bool:
        import sys
        return sys.platform == "win32"
    
    @property
    def is_posix(self) -> bool:
        import os
        return os.name == "posix"
    
    def is_tty(self, fd: int) -> bool:
        import os
        return os.isatty(fd)


def select_launcher(
    platform: PlatformDetector | None = None,
    prefer_pty: bool = True,
) -> ProcessLauncher:
    """Select appropriate launcher for current platform/preferences.
    
    Args:
        platform: Injectable platform detector (default: real detection)
        prefer_pty: Whether to prefer PTY when available
    
    Returns:
        Appropriate ProcessLauncher implementation
    """
    from .pty_launcher import PtyLauncher
    from .subprocess_launcher import SubprocessLauncher
    
    platform = platform or RealPlatformDetector()
    
    if prefer_pty and platform.is_posix and PtyLauncher.is_available():
        return PtyLauncher()
    return SubprocessLauncher()
```

### pty_launcher.py

```python
"""POSIX PTY-based process launcher."""

from __future__ import annotations

import os
import signal
import sys
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any

from meridian.lib.platform import IS_WINDOWS

if TYPE_CHECKING:
    from collections.abc import Callable


class _DeferredUnixModule:
    """Lazy module proxy so Unix-only modules load only on demand."""
    
    def __init__(self, module_name: str) -> None:
        self._module_name = module_name
        self._module: Any | None = None
    
    def _resolve(self) -> Any:
        if self._module is None:
            from importlib import import_module
            self._module = import_module(self._module_name)
        return self._module
    
    def __getattr__(self, name: str) -> Any:
        return getattr(self._resolve(), name)


fcntl = _DeferredUnixModule("fcntl")
termios = _DeferredUnixModule("termios")


class PtyLauncher:
    """POSIX PTY-based process launcher with output capture."""
    
    @staticmethod
    def is_available() -> bool:
        """PTY is available on POSIX systems with a TTY."""
        if IS_WINDOWS:
            return False
        return sys.stdin.isatty() and sys.stdout.isatty()
    
    def launch(
        self,
        command: tuple[str, ...],
        cwd: Path,
        env: dict[str, str],
        output_log_path: Path | None,
        on_started: Callable[[int], None] | None = None,
    ) -> tuple[int, int | None]:
        """Launch command in PTY, copying output to terminal and log."""
        import pty
        
        if output_log_path is None:
            # Fallback to simple subprocess if no capture needed
            from .subprocess_launcher import SubprocessLauncher
            return SubprocessLauncher().launch(command, cwd, env, None, on_started)
        
        # Create PTY and set correct size BEFORE forking
        master_fd, slave_fd = pty.openpty()
        self._sync_pty_winsize(source_fd=sys.stdout.fileno(), target_fd=master_fd)
        
        child_pid = os.fork()
        if child_pid == 0:
            # Child process
            try:
                os.close(master_fd)
                os.login_tty(slave_fd)
                os.chdir(cwd)
                os.execvpe(command[0], command, env)
            except FileNotFoundError:
                os._exit(127)
            except Exception:
                os._exit(1)
        
        # Parent process
        os.close(slave_fd)
        try:
            if on_started is not None:
                try:
                    on_started(child_pid)
                except Exception:
                    with suppress(ProcessLookupError):
                        os.kill(child_pid, signal.SIGTERM)
                    with suppress(ChildProcessError):
                        os.waitpid(child_pid, 0)
                    raise
            
            exit_code = self._copy_pty_output(
                child_pid=child_pid,
                master_fd=master_fd,
                output_log_path=output_log_path,
            )
            return exit_code, child_pid
        finally:
            with suppress(OSError):
                os.close(master_fd)
    
    def _copy_pty_output(
        self,
        child_pid: int,
        master_fd: int,
        output_log_path: Path,
    ) -> int:
        """Copy PTY output to stdout and log file."""
        import select
        import tty
        
        stdin_fd = sys.stdin.fileno()
        stdout_fd = sys.stdout.fileno()
        stdin_open = True
        saved_tty_attrs = None
        
        output_log_path.parent.mkdir(parents=True, exist_ok=True)
        restore_resize = self._install_winsize_forwarding(
            source_fd=stdout_fd,
            target_fd=master_fd,
        )
        
        try:
            if os.isatty(stdin_fd):
                saved_tty_attrs = termios.tcgetattr(stdin_fd)
                tty.setraw(stdin_fd)
            
            with output_log_path.open("wb") as output_handle:
                while True:
                    fds = [master_fd]
                    if stdin_open:
                        fds.append(stdin_fd)
                    ready, _, _ = select.select(fds, [], [])
                    
                    if master_fd in ready:
                        try:
                            chunk = os.read(master_fd, 4096)
                        except OSError:
                            chunk = b""
                        if not chunk:
                            break
                        output_handle.write(chunk)
                        output_handle.flush()
                        os.write(stdout_fd, chunk)
                    
                    if stdin_open and stdin_fd in ready:
                        data = os.read(stdin_fd, 1024)
                        if not data:
                            stdin_open = False
                        else:
                            os.write(master_fd, data)
        finally:
            restore_resize()
            if saved_tty_attrs is not None:
                termios.tcsetattr(stdin_fd, termios.TCSADRAIN, saved_tty_attrs)
        
        _, status = os.waitpid(child_pid, 0)
        return os.waitstatus_to_exitcode(status)
    
    def _sync_pty_winsize(self, *, source_fd: int, target_fd: int) -> None:
        """Copy terminal window size to PTY master."""
        import struct
        try:
            winsize = fcntl.ioctl(
                source_fd,
                termios.TIOCGWINSZ,
                struct.pack("HHHH", 0, 0, 0, 0),
            )
            fcntl.ioctl(target_fd, termios.TIOCSWINSZ, winsize)
        except OSError:
            pass
    
    def _install_winsize_forwarding(
        self,
        *,
        source_fd: int,
        target_fd: int,
    ) -> Callable[[], None]:
        """Sync PTY size now and on future SIGWINCH signals."""
        self._sync_pty_winsize(source_fd=source_fd, target_fd=target_fd)
        
        previous = signal.getsignal(signal.SIGWINCH)
        
        def _handle_resize(signum: int, frame: Any) -> None:
            self._sync_pty_winsize(source_fd=source_fd, target_fd=target_fd)
            if callable(previous):
                previous(signum, frame)
        
        signal.signal(signal.SIGWINCH, _handle_resize)
        
        def _restore() -> None:
            signal.signal(signal.SIGWINCH, previous)
        
        return _restore
```

### subprocess_launcher.py

```python
"""Cross-platform subprocess launcher (no PTY)."""

from __future__ import annotations

import signal
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


class SubprocessLauncher:
    """Simple subprocess launcher for Windows and non-TTY environments."""
    
    @staticmethod
    def is_available() -> bool:
        """Subprocess is always available."""
        return True
    
    def launch(
        self,
        command: tuple[str, ...],
        cwd: Path,
        env: dict[str, str],
        output_log_path: Path | None,
        on_started: Callable[[int], None] | None = None,
    ) -> tuple[int, int | None]:
        """Launch command as subprocess without PTY."""
        # Note: output_log_path is ignored for subprocess mode
        # (PTY capture requires PTY; this is fallback)
        _ = output_log_path
        
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            text=True,
        )
        
        if on_started is not None:
            try:
                on_started(process.pid)
            except Exception:
                if process.poll() is None:
                    process.terminate()
                    process.wait()
                raise
        
        try:
            return process.wait(), process.pid
        except KeyboardInterrupt:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
                return process.wait(), process.pid
            return 130, process.pid
```

### session.py

```python
"""Session lifecycle management extracted from run_harness_process."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from meridian.lib.core.types import SpawnId
    from meridian.lib.core.clock import Clock
    from meridian.lib.launch.streaming.adapters import SpawnStoreAdapter


@dataclass
class SessionMetadata:
    """Metadata for session creation."""
    harness: str
    model: str
    agent: str
    agent_path: str
    skills: tuple[str, ...]
    skill_paths: tuple[str, ...]


class SessionManager:
    """Manages session lifecycle with injectable dependencies."""
    
    def __init__(
        self,
        *,
        state_root: Path,
        clock: Clock,
        spawn_store: SpawnStoreAdapter,
    ) -> None:
        self._state_root = state_root
        self._clock = clock
        self._spawn_store = spawn_store
    
    def start_primary_spawn(
        self,
        *,
        chat_id: str,
        metadata: SessionMetadata,
        prompt: str,
        # ... other params
    ) -> SpawnId:
        """Create spawn record for primary session."""
        # ... extracted logic from run_harness_process
        pass
    
    def finalize_spawn(
        self,
        spawn_id: SpawnId,
        exit_code: int,
        duration_secs: float | None,
    ) -> None:
        """Finalize spawn after process exit."""
        # ... extracted logic
        pass
```

---

## Test Migration

### Before (PTY tests require real fork)
```python
@pytest.mark.posix_only
def test_primary_process_with_pty(tmp_path, ...):
    # Must run real fork/pty
    exit_code, pid = _run_primary_process_with_capture(...)
```

### After (unit tests use fake launcher)
```python
from tests.support.fakes import FakeProcessLauncher

def test_primary_process_lifecycle():
    """Unit test: verify session lifecycle without real subprocess."""
    fake_launcher = FakeProcessLauncher(results={
        ("echo", "hello"): (0, "hello\n", ""),
    })
    
    # Test session manager with fake launcher
    ...

@pytest.mark.posix_only
def test_pty_output_capture(tmp_path):
    """Integration test: real PTY on POSIX."""
    launcher = PtyLauncher()
    assert launcher.is_available()
    exit_code, _ = launcher.launch(("echo", "test"), ...)
    assert exit_code == 0
```

---

## Platform Testing Strategy

| Test Type | Location | Runs On |
|-----------|----------|---------|
| Launcher selection logic | `tests/unit/launch/` | All platforms |
| Session lifecycle | `tests/unit/launch/` | All platforms |
| PTY mechanics | `tests/platform/posix/` | Linux/macOS |
| Subprocess fallback | `tests/integration/launch/` | All platforms |
| Windows file handles | `tests/platform/windows/` | Windows |
