# Streaming Runner — Behavioral Specification

## Module Responsibilities After Split

The current `streaming_runner.py` (1244 lines) mixes:
- Orchestration (async task coordination, signal handling)
- Retry policy (decision logic for when/how to retry)
- Heartbeat management (file touching, interval timing)
- Terminal event classification (harness-specific protocol parsing)
- Spawn-store integration (state persistence)

After splitting, each file has ONE responsibility.

---

## streaming/decision.py — Pure Decision Logic

**[SPEC-SR-DEC-001]** WHEN `should_retry()` is called with exit code, stderr, and attempt count, it SHALL return a boolean decision based on:
- Error category classification
- Retry budget remaining
- Timeout status
- Strategy change signals in stderr

**[SPEC-SR-DEC-002]** WHEN `classify_error()` is called, it SHALL categorize the failure into: TRANSIENT, PERMANENT, STRATEGY_CHANGE, or UNKNOWN based on stderr patterns and exit codes.

**[SPEC-SR-DEC-003]** WHEN `terminal_event_outcome()` is called with a harness event, it SHALL return `TerminalEventOutcome` or `None` based on harness-specific terminal event patterns:
- Claude: `result` event with success/error subtype
- Codex: `turn/completed` event
- OpenCode: `session.idle` or `session.error` events

**[SPEC-SR-DEC-004]** The decision module SHALL NOT import asyncio, signal, os, or pathlib — it operates on pure data only.

**[SPEC-SR-DEC-005]** WHEN tests verify retry logic, they SHALL call decision functions directly with constructed inputs, without mocking.

---

## streaming/heartbeat.py — Heartbeat Management

**[SPEC-SR-HB-001]** WHEN `HeartbeatManager` is constructed, it SHALL accept:
- `interval_secs: float` — heartbeat interval
- `clock: Clock` — injectable time source
- `touch_fn: Callable[[Path, SpawnId], None]` — injectable file touch operation

**[SPEC-SR-HB-002]** WHEN `start_heartbeat()` is called, it SHALL schedule periodic heartbeat touches using the injected interval and clock.

**[SPEC-SR-HB-003]** WHEN `stop_heartbeat()` is called, it SHALL cancel pending heartbeat operations gracefully.

**[SPEC-SR-HB-004]** WHEN tests verify heartbeat timing, they SHALL inject a `FakeClock` and advance time explicitly, without `monkeypatch.setattr` on module constants.

---

## streaming/runner.py — Thin Orchestration Shell

**[SPEC-SR-RUN-001]** WHEN `execute_with_streaming()` is called, it SHALL compose the decision engine, heartbeat manager, and spawn-store adapter to execute one spawn.

**[SPEC-SR-RUN-002]** WHEN the runner needs spawn-store operations, it SHALL call through the injected `SpawnStoreAdapter` rather than importing `spawn_store` directly.

**[SPEC-SR-RUN-003]** WHEN the runner handles signals, it SHALL use the injected `SignalCoordinator` to mask/unmask SIGTERM during cleanup.

**[SPEC-SR-RUN-004]** The orchestration shell SHALL contain NO branching logic beyond task coordination — all decisions delegate to decision.py.

**[SPEC-SR-RUN-005]** WHEN tests verify orchestration behavior, they SHALL provide fake adapters and verify the sequence of adapter calls, not internal state.

---

## streaming/adapters.py — Protocol Definitions

**[SPEC-SR-ADP-001]** The `Clock` protocol SHALL define:
```python
class Clock(Protocol):
    def monotonic(self) -> float: ...
    def time(self) -> float: ...
```

**[SPEC-SR-ADP-002]** The `HeartbeatAdapter` protocol SHALL define:
```python
class HeartbeatAdapter(Protocol):
    def touch(self, state_root: Path, spawn_id: SpawnId) -> None: ...
```

**[SPEC-SR-ADP-003]** The `SpawnStoreAdapter` protocol SHALL define:
```python
class SpawnStoreAdapter(Protocol):
    def update_spawn(self, spawn_id: SpawnId, **kwargs) -> None: ...
    def mark_finalizing(self, spawn_id: SpawnId) -> bool: ...
    def finalize_spawn(self, spawn_id: SpawnId, ...) -> bool: ...
    def record_spawn_exited(self, spawn_id: SpawnId, exit_code: int) -> None: ...
```

**[SPEC-SR-ADP-004]** The `SignalCoordinator` protocol SHALL define:
```python
class SignalCoordinator(Protocol):
    def mask_sigterm(self) -> ContextManager[None]: ...
```

**[SPEC-SR-ADP-005]** Each protocol SHALL have a production implementation in the same file AND a fake implementation in `tests/support/fakes.py`.

---

## Runtime Value Justification

These abstractions provide value beyond testing:

1. **Clock injection** — Enables deterministic replay of timing-sensitive scenarios, useful for debugging production issues.

2. **HeartbeatAdapter** — Allows future extension to remote heartbeat protocols without changing orchestration logic.

3. **SpawnStoreAdapter** — Enables future alternate storage backends (e.g., SQLite, remote) without touching runner code.

4. **SignalCoordinator** — Already exists for Windows compatibility; this formalizes the interface.
