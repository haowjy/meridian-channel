# Process Module — Behavioral Specification

## Module Responsibilities After Split

The current `process.py` (570 lines) mixes:
- PTY/subprocess mechanics (fork, openpty, tty configuration)
- Session management (session_scope integration, harness session IDs)
- Primary launch orchestration (compose context, start spawn, wait, finalize)
- Window size forwarding (SIGWINCH handling, ioctl calls)
- Platform branching (Windows vs POSIX paths)

After splitting, each file has ONE responsibility.

---

## process/pty_launcher.py — PTY/Subprocess Mechanics

**[SPEC-PR-PTY-001]** WHEN `PtyLauncher` executes a command, it SHALL:
- Create a PTY pair with correct window size from the start
- Fork and exec the command in the child
- Copy PTY output to stdout while logging to file

**[SPEC-PR-PTY-002]** WHEN the system runs on Windows, `PtyLauncher.is_available()` SHALL return `False` and launch SHALL fall back to basic subprocess.

**[SPEC-PR-PTY-003]** WHEN a test needs to verify PTY behavior, it SHALL be marked `posix_only` and run real fork/pty operations.

**[SPEC-PR-PTY-004]** WHEN a test needs to verify process lifecycle WITHOUT PTY, it SHALL inject a `FakeProcessLauncher` that simulates exit codes without fork.

---

## process/session.py — Session Management

**[SPEC-PR-SES-001]** WHEN `SessionManager` starts a session, it SHALL:
- Create session scope with appropriate metadata
- Handle resume vs fresh vs fork session modes
- Record harness session ID observations

**[SPEC-PR-SES-002]** WHEN session management interacts with spawn_store, it SHALL use the injected `SpawnStoreAdapter` rather than direct imports.

**[SPEC-PR-SES-003]** WHEN session management accesses time, it SHALL use the injected `Clock` rather than `time.time()` / `time.monotonic()`.

**[SPEC-PR-SES-004]** WHEN tests verify session lifecycle, they SHALL inject fake adapters and verify state transitions without real subprocess execution.

---

## process/runner.py — Thin Orchestration

**[SPEC-PR-RUN-001]** WHEN `run_harness_process()` is called, it SHALL compose:
- `LaunchContext` from request
- `SessionManager` for session lifecycle
- `PtyLauncher` or `SubprocessLauncher` based on platform/capabilities
- `SpawnStoreAdapter` for state persistence

**[SPEC-PR-RUN-002]** The runner SHALL NOT contain platform-specific code — it delegates to launchers.

**[SPEC-PR-RUN-003]** WHEN the process exits, the runner SHALL call `finalize_spawn()` through the adapter, not direct spawn_store import.

---

## ports.py — Protocol Definitions

**[SPEC-PR-PRT-001]** The `ProcessLauncher` protocol SHALL define:
```python
class ProcessLauncher(Protocol):
    def launch(
        self,
        command: tuple[str, ...],
        cwd: Path,
        env: dict[str, str],
        output_log_path: Path | None,
        on_started: Callable[[int], None] | None,
    ) -> tuple[int, int | None]: ...  # (exit_code, child_pid)
    
    @staticmethod
    def is_available() -> bool: ...
```

**[SPEC-PR-PRT-002]** The `Clock` protocol SHALL be shared with streaming/adapters.py to avoid duplication.

**[SPEC-PR-PRT-003]** Platform-specific implementations SHALL live in `process/pty_launcher.py` (POSIX) and `process/subprocess_launcher.py` (cross-platform fallback).

---

## Platform Isolation

**[SPEC-PR-PLT-001]** WHEN Unix-only modules (fcntl, termios, pty) are needed, they SHALL be imported lazily via `_DeferredUnixModule` pattern (already exists).

**[SPEC-PR-PLT-002]** WHEN tests simulate Windows behavior on Linux, they SHALL inject `is_windows=True` to the launcher selector rather than monkeypatching `IS_WINDOWS`.

**[SPEC-PR-PLT-003]** WHEN real Windows testing is needed, tests SHALL be marked `windows_only` and run on Windows CI.

---

## Runtime Value Justification

1. **ProcessLauncher protocol** — Enables future alternative launch mechanisms (containers, remote execution) without changing runner code.

2. **Session management separation** — Makes session lifecycle testable independently from process execution.

3. **Platform abstraction** — Required for Windows support; the refactor formalizes an existing necessity.
