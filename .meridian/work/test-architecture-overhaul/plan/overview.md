# Test Architecture Overhaul — Implementation Plan

Based on DESIGN.md, this is a 7-phase implementation with atomic commits.

## Phase Sequence

### Phase 0: Foundation
Commits:
- 0.1: Create `lib/core/clock.py` with Clock protocol + RealClock
- 0.2: Create `tests/support/` with FakeClock
- 0.3: Add marker registration to `tests/conftest.py`
- 0.4: Centralize lazy Unix proxy in `lib/platform/unix_modules.py`
- 0.5: Update `process.py` to import from `lib/platform/`
- 0.6: Update `session_store.py` to import from `lib/platform/`

### Phase 1: Pure Logic Extraction
Commits:
- 1.1: Create `lib/state/spawn/events.py` with reduce_events()
- 1.2: Move logic, re-export from spawn_store.py
- 1.3: Add unit tests in tests/unit/state/
- 1.4: Create `lib/launch/streaming/decision.py`
- 1.5: Move terminal_event_outcome(), re-export
- 1.6: Add unit tests in tests/unit/launch/

### Phase 2-6: See DESIGN.md

## Constraints
- Atomic commits per step
- Each commit must pass tests
- Backward-compatible re-exports from original paths
- No test-induced design damage
