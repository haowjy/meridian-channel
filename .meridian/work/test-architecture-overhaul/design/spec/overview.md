# Test Architecture Overhaul — Behavioral Specification

## Scope

This specification defines the behavioral contract for the meridian-cli test architecture overhaul, covering two tracks:

1. **Production code refactoring** — Splitting monolithic files into single-purpose modules with injectable dependencies
2. **Test architecture** — Establishing a coherent test structure with clear separation, reusable fixtures, and CI slicing

## EARS Notation Key

- **[SPEC-XXX]** — Stable identifier for traceability
- **WHEN** — Trigger condition
- **SHALL** — Mandatory behavior
- **MAY** — Optional behavior
- **IF** — Conditional clause

---

## Track 1: Production Code Testability

### streaming_runner.py Split

**[SPEC-SR-001]** WHEN the streaming runner executes a spawn, the system SHALL separate orchestration (task coordination, signal handling, retry loop) from pure decision logic (retry policy evaluation, state transitions).

**[SPEC-SR-002]** WHEN a test needs to verify heartbeat behavior, the system SHALL provide an injectable clock and heartbeat interval rather than requiring monkeypatch of module-level constants.

**[SPEC-SR-003]** WHEN the streaming runner touches the heartbeat file, the system SHALL call through an injectable `HeartbeatAdapter` protocol rather than direct filesystem access.

**[SPEC-SR-004]** WHEN the streaming runner needs to track spawn state, the system SHALL accept a `SpawnStoreAdapter` protocol at construction rather than importing spawn_store module directly.

**[SPEC-SR-005]** WHEN the streaming runner handles signals, the system SHALL use an injectable signal coordinator that can be replaced with a fake for unit tests.

### process.py Split

**[SPEC-PR-001]** WHEN a test verifies primary process launch behavior, the system SHALL allow injection of a process launcher rather than requiring fork/pty in every test.

**[SPEC-PR-002]** WHEN the process module needs current time, the system SHALL call through an injectable `Clock` protocol rather than calling `time.time()` or `time.monotonic()` directly.

**[SPEC-PR-003]** WHEN the process module accesses platform-specific APIs (pty, fcntl, termios), the system SHALL isolate these behind narrow interfaces that tests can stub on non-POSIX platforms.

**[SPEC-PR-004]** WHEN the system runs on Windows, platform-specific behavior SHALL degrade gracefully with clear capability boundaries rather than runtime import errors.

### spawn_store.py Split

**[SPEC-SS-001]** WHEN a test verifies spawn state projection logic, the system SHALL provide a pure `_record_from_events()` function that operates on in-memory event lists without filesystem access.

**[SPEC-SS-002]** WHEN spawn_store writes events to JSONL, the system SHALL use an injectable `FileAdapter` that tests can replace with in-memory implementations.

**[SPEC-SS-003]** WHEN spawn_store generates timestamps, the system SHALL use an injectable clock rather than calling `utc_now_iso()` directly.

**[SPEC-SS-004]** WHEN spawn_store checks process liveness, the system SHALL use an injectable process checker rather than direct `os.kill(pid, 0)` calls.

---

## Track 2: Test Architecture

### Directory Structure

**[SPEC-TD-001]** WHEN pytest collects tests, the system SHALL organize tests into distinct directories by test type: `unit/`, `integration/`, `contract/`, `platform/`, `e2e/`.

**[SPEC-TD-002]** WHEN a unit test runs, it SHALL NOT perform real filesystem I/O, subprocess execution, or network calls.

**[SPEC-TD-003]** WHEN an integration test runs, it SHALL interact with exactly one real boundary (filesystem OR subprocess OR network), using tmp_path for isolation.

**[SPEC-TD-004]** WHEN a platform test runs, it SHALL be marked with `posix_only` or `windows_only` and skipped on incompatible platforms.

**[SPEC-TD-005]** WHEN an e2e test runs, it SHALL invoke the installed CLI binary as an external user would, testing critical paths only.

### Markers and CI

**[SPEC-MK-001]** WHEN pytest configures markers, the system SHALL register: `unit`, `integration`, `e2e`, `contract`, `posix_only`, `windows_only`, `slow`.

**[SPEC-MK-002]** WHEN CI runs the fast gate, it SHALL execute `pytest -m "unit or (integration and not slow)"` completing in under 60 seconds.

**[SPEC-MK-003]** WHEN CI runs the full gate, it SHALL execute all tests except platform-incompatible ones, completing in under 5 minutes.

**[SPEC-MK-004]** WHEN Windows CI runs, it SHALL execute `pytest -m "not posix_only"` to validate Windows-specific behavior.

### Fixtures

**[SPEC-FX-001]** WHEN a test needs a fake clock, it SHALL use the shared `FakeClock` fixture from `tests/support/fakes.py` rather than creating ad-hoc implementations.

**[SPEC-FX-002]** WHEN a test needs a state root, it SHALL use the factory fixture `state_root_factory` that creates isolated tmp_path-based roots.

**[SPEC-FX-003]** WHEN a test needs a fake subprocess result, it SHALL use the shared `FakeSubprocess` from `tests/support/fakes.py`.

**[SPEC-FX-004]** WHEN a conftest.py file imports helper code, it SHALL import from `tests/support/` modules rather than using intra-conftest imports.

**[SPEC-FX-005]** WHEN fixtures provide cleanup, they SHALL use `yield` pattern with cleanup in the finally block rather than return + separate cleanup.

### Migration

**[SPEC-MG-001]** WHEN migrating existing tests, the system SHALL first add markers to existing tests (tag phase) without moving files.

**[SPEC-MG-002]** WHEN migrating existing tests, the system SHALL then move tagged tests to appropriate directories (move phase) maintaining test identity.

**[SPEC-MG-003]** WHEN migrating existing tests, the system SHALL finally rewrite brittle tests using new fixtures (rewrite phase) as a separate commit.

**[SPEC-MG-004]** WHEN a test is migrated, the total test count SHALL NOT decrease — deleted tests require explicit replacement.

---

## Cross-Cutting Concerns

### No Test-Induced Design Damage

**[SPEC-CC-001]** WHEN introducing an abstraction for testability, that abstraction SHALL provide runtime value (configuration, observability, or extensibility) beyond just easier mocking.

**[SPEC-CC-002]** IF an abstraction exists solely to enable testing, the design SHALL reconsider whether the underlying code's responsibility boundaries are correct.

### Incremental Migration

**[SPEC-CC-003]** WHEN refactoring production code, the existing tests SHALL continue to pass at each commit — no "big bang" rewrites.

**[SPEC-CC-004]** WHEN adding new test infrastructure, it SHALL coexist with existing tests until migration is complete.

### Windows Testability

**[SPEC-CC-005]** WHEN platform detection affects behavior, the system SHALL allow injection of platform identity for simulation testing on Linux.

**[SPEC-CC-006]** WHEN testing Windows-specific behavior, real Windows CI SHALL validate signal handling, file locking, and NTFS edge cases.
