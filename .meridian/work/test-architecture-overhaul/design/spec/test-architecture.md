# Test Architecture — Behavioral Specification

## Directory Structure Contracts

### Unit Tests (tests/unit/)

**[SPEC-TA-UN-001]** WHEN a test lives in `tests/unit/`, it SHALL:
- Execute in under 100ms per test
- Use no real filesystem I/O (no tmp_path, no file creation)
- Use no real subprocess execution
- Use no real network calls
- Use only in-memory fakes and pure function calls

**[SPEC-TA-UN-002]** WHEN a unit test needs external state, it SHALL inject fakes from `tests/support/fakes.py`.

**[SPEC-TA-UN-003]** WHEN a unit test verifies behavior, it SHALL be automatically marked `@pytest.mark.unit` by conftest.py based on directory.

**[SPEC-TA-UN-004]** Unit test directories SHALL mirror production code structure:
```
tests/unit/
  state/          # Tests for state layer pure functions
  launch/         # Tests for launch decision logic
  harness/        # Tests for harness projection/parsing
  core/           # Tests for core domain logic
```

### Integration Tests (tests/integration/)

**[SPEC-TA-IN-001]** WHEN a test lives in `tests/integration/`, it SHALL:
- Interact with exactly ONE real boundary (filesystem OR subprocess OR network)
- Use tmp_path for filesystem isolation
- Clean up all resources on exit

**[SPEC-TA-IN-002]** WHEN an integration test uses the filesystem, it SHALL use the `state_root_factory` fixture that provides isolated tmp_path roots.

**[SPEC-TA-IN-003]** WHEN an integration test uses subprocess, it SHALL use controlled test binaries or timeout guards.

**[SPEC-TA-IN-004]** WHEN a test takes longer than 1 second, it SHALL be marked `@pytest.mark.slow`.

**[SPEC-TA-IN-005]** Integration test directories SHALL organize by boundary type:
```
tests/integration/
  state/          # Real filesystem, fake subprocess
  launch/         # Real subprocess, controlled binaries
  cli/            # Real CLI invocation, isolated state root
```

### Contract Tests (tests/contract/)

**[SPEC-TA-CT-001]** WHEN a contract test runs, it SHALL verify parity between components:
- Harness launch spec generation vs harness expectations
- Event serialization vs parsing round-trip
- Adapter implementations vs protocol contracts

**[SPEC-TA-CT-002]** WHEN a protocol has multiple implementations, each SHALL have a contract test verifying protocol compliance.

**[SPEC-TA-CT-003]** Contract tests SHALL NOT test business logic — only interface contracts.

### Platform Tests (tests/platform/)

**[SPEC-TA-PL-001]** WHEN a test verifies POSIX-specific behavior (signals, pty, fork), it SHALL:
- Live in `tests/platform/posix/`
- Be marked `@pytest.mark.posix_only`
- Skip on Windows with clear reason

**[SPEC-TA-PL-002]** WHEN a test verifies Windows-specific behavior (file locking, console), it SHALL:
- Live in `tests/platform/windows/`
- Be marked `@pytest.mark.windows_only`
- Skip on non-Windows with clear reason

**[SPEC-TA-PL-003]** WHEN a test verifies cross-platform behavior using platform detection, it SHALL:
- Live in appropriate unit/integration directory
- Inject platform identity rather than monkeypatching IS_WINDOWS

### E2E Tests (tests/e2e/)

**[SPEC-TA-E2-001]** WHEN an e2e test runs, it SHALL invoke the installed CLI binary as an external process.

**[SPEC-TA-E2-002]** E2E tests SHALL cover critical paths only:
- Basic spawn create/list/show lifecycle
- CLI help and version commands
- Configuration loading

**[SPEC-TA-E2-003]** E2E tests SHALL NOT duplicate integration test coverage — they verify the full stack works together.

**[SPEC-TA-E2-004]** WHEN e2e tests timeout, they SHALL have explicit timeout markers: `@pytest.mark.timeout(30)`.

---

## Fixture Contracts

### FakeClock

**[SPEC-FX-CL-001]** WHEN `FakeClock` is constructed, it SHALL accept optional `start: float = 0.0`.

**[SPEC-FX-CL-002]** WHEN `FakeClock.monotonic()` is called, it SHALL return current fake time.

**[SPEC-FX-CL-003]** WHEN `FakeClock.time()` is called, it SHALL return current fake time (epoch-style).

**[SPEC-FX-CL-004]** WHEN `FakeClock.advance(seconds)` is called, it SHALL add seconds to both monotonic and time values.

**[SPEC-FX-CL-005]** WHEN `FakeClock.set(value)` is called, it SHALL set absolute time for both clocks.

### FakeFileAdapter

**[SPEC-FX-FA-001]** WHEN `FakeFileAdapter` is constructed, it SHALL maintain an in-memory dict[Path, list[str]] for file contents.

**[SPEC-FX-FA-002]** WHEN `read_lines()` is called for missing file, it SHALL return empty list (no exception).

**[SPEC-FX-FA-003]** WHEN `append_line()` is called, it SHALL append to in-memory list, creating if needed.

### FakeSubprocess

**[SPEC-FX-SP-001]** WHEN `FakeSubprocess` is constructed, it SHALL accept a `results: dict[tuple[str, ...], tuple[int, str, str]]` mapping commands to (exit_code, stdout, stderr).

**[SPEC-FX-SP-002]** WHEN `run()` is called for unknown command, it SHALL return exit_code=127.

**[SPEC-FX-SP-003]** FakeSubprocess SHALL record call history for verification.

### StateRootFactory

**[SPEC-FX-SR-001]** WHEN `state_root_factory` is called, it SHALL return a function that creates isolated tmp_path-based state roots.

**[SPEC-FX-SR-002]** WHEN the factory creates a root, it SHALL create required subdirectories (spawns/, sessions/, artifacts/).

**[SPEC-FX-SR-003]** WHEN the test ends, all created roots SHALL be cleaned up automatically.

---

## Marker Contracts

**[SPEC-MK-REG-001]** The following markers SHALL be registered in root conftest.py:
- `unit` — Pure logic tests, auto-applied to tests/unit/
- `integration` — One real boundary, auto-applied to tests/integration/
- `e2e` — Full CLI invocation
- `contract` — Parity/drift checks
- `posix_only` — Requires POSIX semantics
- `windows_only` — Requires Windows semantics
- `slow` — Takes longer than 1 second

**[SPEC-MK-AUTO-001]** WHEN a test lives in `tests/unit/`, the `unit` marker SHALL be applied automatically via conftest.py hook.

**[SPEC-MK-AUTO-002]** WHEN a test lives in `tests/integration/`, the `integration` marker SHALL be applied automatically.

**[SPEC-MK-STRCT-001]** Unknown markers SHALL cause pytest to fail with `--strict-markers`.

---

## Migration Contracts

**[SPEC-MG-TAG-001]** WHEN tagging phase completes, every existing test file SHALL have explicit markers indicating test type.

**[SPEC-MG-TAG-002]** WHEN tagging phase completes, `pytest -m unit` and `pytest -m integration` SHALL produce non-empty results.

**[SPEC-MG-MOV-001]** WHEN move phase completes, tests/unit/ and tests/integration/ SHALL contain the majority of tests.

**[SPEC-MG-MOV-002]** WHEN move phase completes, `pytest` (all tests) SHALL produce the same pass/fail results as before migration.

**[SPEC-MG-RWR-001]** WHEN rewrite phase targets a test, the test SHALL be rewritten to use shared fixtures instead of inline fakes.

**[SPEC-MG-RWR-002]** WHEN rewrite phase completes for a file, that file SHALL NOT contain `monkeypatch.setattr` calls on module-level constants.
