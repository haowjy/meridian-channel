# Phase 1: Pure Logic Extraction

## Objective
Extract pure decision logic from spawn_store.py and streaming_runner.py into separate modules for unit testing.

## Commits (Execute in Order)

### Commit 1.1: Create lib/state/spawn/events.py Structure
Create directory structure:
```
src/meridian/lib/state/spawn/
├── __init__.py       # Re-exports for backward compat
└── events.py         # Pure event reducer logic
```

`events.py` should contain:
- Import SpawnRecord and event types from spawn_store.py (temporarily, will refactor imports later)
- Empty `reduce_events()` function stub

Validation: Import works

### Commit 1.2: Move _record_from_events Logic
Move from `spawn_store.py`:
- `_empty_record()` function
- `_normalized_work_id()` function  
- `_record_from_events()` → rename to `reduce_events()` and make public

In `spawn_store.py`:
- Import `reduce_events` from `state.spawn.events`
- Create backward compat alias: `_record_from_events = reduce_events`
- Update all internal calls to use `reduce_events`

Validation: Existing tests pass

### Commit 1.3: Add Unit Tests for reduce_events
Create `tests/unit/state/__init__.py` and `tests/unit/state/test_events.py`:

Test cases:
- Empty event list returns empty dict
- Single start event creates record
- Update event modifies record
- Exited event records exit code
- Finalize event sets terminal state
- Multiple events for same spawn merge correctly
- Events for different spawns stay separate

Mark tests with `@pytest.mark.unit`

Validation: New tests pass

### Commit 1.4: Create lib/launch/streaming/decision.py Structure
Create directory structure:
```
src/meridian/lib/launch/streaming/
├── __init__.py       # Re-exports
└── decision.py       # Pure terminal event classification
```

`decision.py` should contain:
- TerminalEventOutcome dataclass (moved from streaming_runner.py)
- `_stringify_terminal_error()` helper (moved)
- `terminal_event_outcome()` function stub

Validation: Import works

### Commit 1.5: Move terminal_event_outcome Logic
Move from `streaming_runner.py`:
- `TerminalEventOutcome` dataclass
- `_stringify_terminal_error()` function
- `terminal_event_outcome()` function

In `streaming_runner.py`:
- Import from `launch.streaming.decision`
- Re-export for backward compat

Validation: Existing tests pass

### Commit 1.6: Add Unit Tests for terminal_event_outcome
Create `tests/unit/launch/__init__.py` and `tests/unit/launch/test_decision.py`:

Test cases:
- Codex turn/completed → succeeded
- Claude result with success → succeeded  
- Claude result with error → failed
- OpenCode session.idle → succeeded
- OpenCode session.error → failed
- error/connectionClosed → failed
- Unknown event → None

Mark tests with `@pytest.mark.unit`

Validation: New tests pass

## Files to Touch
- Create: `src/meridian/lib/state/spawn/__init__.py`
- Create: `src/meridian/lib/state/spawn/events.py`
- Modify: `src/meridian/lib/state/spawn_store.py`
- Create: `src/meridian/lib/launch/streaming/__init__.py`
- Create: `src/meridian/lib/launch/streaming/decision.py`
- Modify: `src/meridian/lib/launch/streaming_runner.py`
- Create: `tests/unit/__init__.py`, `tests/unit/conftest.py`
- Create: `tests/unit/state/__init__.py`, `tests/unit/state/test_events.py`
- Create: `tests/unit/launch/__init__.py`, `tests/unit/launch/test_decision.py`

## Exit Criteria
- All 6 commits made atomically
- Each commit passes pytest
- `from meridian.lib.state.spawn.events import reduce_events` works
- `from meridian.lib.launch.streaming.decision import terminal_event_outcome` works
- Original imports still work (backward compat)
- New unit tests pass
