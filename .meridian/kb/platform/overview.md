# Platform

Cross-platform OS primitives used across the codebase. Collapses OS-specific branches that used to live inline in multiple modules behind narrow adapters so callers stay OS-neutral.

Source: `src/meridian/lib/platform/`

## Why This Module Exists

Windows support is a product requirement (CLAUDE.md #6). Before this module, platform branches (`fcntl` vs `msvcrt`, signal handling, fsync) were scattered inline across `state/`, `launch/`, and `streaming/`. Concentrating them here follows CLAUDE.md #7 (prefer cross-platform abstractions over handwritten branches): callers import `lock_file` or `terminate_tree` and never touch OS conditionals.

## Module Map

```
src/meridian/lib/platform/
├── __init__.py      — IS_WINDOWS / IS_POSIX, get_home_path(), re-exports from unix_modules.py
├── unix_modules.py  — DeferredUnixModule class + shared fcntl/pty/select/termios/tty proxies
├── locking.py       — lock_file() context manager: exclusive file lock, thread-local reentrant
└── terminate.py     — terminate_tree() async helper: SIGTERM → grace → SIGKILL process tree kill
```

## OS Detection — `__init__.py`

```python
IS_WINDOWS: bool   # sys.platform == "win32"
IS_POSIX:   bool   # not IS_WINDOWS
```

Prefer these over inline `sys.platform` comparisons — consistent spelling, importable as a named concept, easy to grep.

## Home Directory — `get_home_path()`

```python
def get_home_path() -> Path: ...
```

Returns home directory, respecting the `HOME` env var for test isolation. On POSIX, `Path.home()` already respects `HOME`; on Windows, `Path.home()` queries Windows APIs and ignores `HOME`, which breaks test isolation. `get_home_path()` checks `HOME` first (if non-empty) and falls back to `Path.home()`.

Used by `state/user_paths.py` for `%LOCALAPPDATA%`/`~/.meridian` resolution, and by harness adapters/extractors (`claude`, `codex`, `opencode`, `claude_preflight`, `opencode_storage`, extractors) to locate per-harness home directories.

## File Locking — `locking.py`

```python
@contextmanager
def lock_file(lock_path: Path) -> Iterator[IO[bytes]]: ...
```

Acquires an exclusive file lock for the duration of the `with` block. Used by state stores to serialize concurrent writes. Confirmed callers: `state/event_store.py` (JSONL appends for spawns/sessions), `state/session_store.py` (session event writes and session-id-counter), `state/work_store.py` (work item mutations), `state/user_paths.py` (UUID creation under `id.lock`). `state/atomic.py` does NOT call `lock_file`.

**Behavior:**
- **Thread-local reentrancy:** a thread that already holds the lock can re-enter `lock_file` on the same path without deadlocking. A per-thread depth counter tracks nesting; the underlying OS lock is released only on the outermost exit.
- **POSIX:** `fcntl.flock(LOCK_EX)` — advisory, kernel-backed.
- **Windows:** `msvcrt.locking(LK_NBLCK, 1)` with a retry loop (50 ms sleep). Locks a 1-byte region at offset 0 (NTFS requires a non-zero-length file; the implementation writes a guard byte and flushes before locking). Released via `LK_UNLCK`.

`fcntl` is accessed through the shared `platform` proxy (`from meridian.lib.platform import fcntl`) rather than imported inline. `msvcrt` is imported function-locally inside `_acquire_windows_lock`/`_release_windows_lock`. See [deferred imports](#deferred-import-pattern) below.

## Process Tree Termination — `terminate.py`

```python
async def terminate_tree(
    process: asyncio.subprocess.Process,
    *,
    grace_secs: float = 5.0,
) -> None: ...
```

Terminates `process` and all its descendants. Used by the launch layer when a spawn is cancelled or times out.

**Sequence:**
1. Snapshot root + children via `psutil` *before* sending signals (avoids races where children fork after the root exits).
2. Send `SIGTERM` (Windows: `TerminateProcess` via psutil) to every process in the tree, children first.
3. `asyncio.to_thread(psutil.wait_procs, tree, timeout=grace_secs)` — async-safe wait.
4. If any processes survive: send `SIGKILL` / force-kill and wait up to 1 second.

**Why psutil:** it already handles cross-platform PID/tree semantics and process-not-found races (`NoSuchProcess`, `AccessDenied`) without additional transitive dependencies. Avoids hand-rolling OS-specific child enumeration (`/proc` on Linux, `NtQueryInformationProcess` on Windows).

Returns immediately if `process.returncode is not None` (already exited).

## Deferred-Import Pattern

`fcntl`, `pty`, `termios`, `tty`, and `msvcrt` are POSIX-only or Windows-only stdlib modules that raise `ImportError` on the other platform if imported at module top. Two patterns gate these imports:

**(a) Module-level lazy proxy (`DeferredUnixModule`):** defined in `platform/unix_modules.py`, which also instantiates the shared proxies `fcntl`, `pty`, `select`, `termios`, `tty`. These are re-exported from `meridian.lib.platform.__init__`. Callers import the shared proxies directly — e.g., `from meridian.lib.platform import fcntl, pty, select, termios, tty` — rather than declaring their own instances. Confirmed consumers: `platform/locking.py` (`fcntl`), `launch/process/pty_launcher.py` (`fcntl, pty, select, termios, tty`). The proxy forwards attribute access to the real module on first use, so the package imports cleanly on Windows.

**(b) Inline function-local import:** `platform/locking.py` imports `msvcrt` inside `_acquire_windows_lock`/`_release_windows_lock`. This keeps the Windows-only import scoped to Windows-only code paths.

Both patterns make all platform modules importable on all OSes, enabling `import meridian` to succeed without branching the import path.

## Directory fsync

`_fsync_directory(path)` in `state/atomic.py` syncs the parent directory after a file rename to guarantee durability. On Windows it early-returns immediately — NTFS is a journaling filesystem and does not require the caller to fsync the parent directory; attempting it raises `PermissionError`.

Called from:
- `atomic_write_text` and `atomic_write_bytes` — after every `os.replace()`
- `append_text_line` — on first-create only (when the file did not exist before the append)
