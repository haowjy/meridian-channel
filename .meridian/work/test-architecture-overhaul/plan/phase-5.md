# Phase 5: Test Migration

## Objective
Create proper test directory structure and migrate tests incrementally.

## Commits (Execute in Order)

### Commit 5.1: Create Test Directory Structure
Create directories with conftest.py files:
```
tests/
├── unit/
│   ├── __init__.py
│   ├── conftest.py      # Auto-marker hook for @pytest.mark.unit
│   ├── state/
│   │   └── __init__.py
│   └── launch/
│       └── __init__.py
├── integration/
│   ├── __init__.py
│   ├── conftest.py      # Auto-marker hook for @pytest.mark.integration
│   ├── state/
│   │   └── __init__.py
│   ├── launch/
│   │   └── __init__.py
│   └── cli/
│       └── __init__.py
├── contract/
│   ├── __init__.py
│   ├── conftest.py      # Auto-marker hook for @pytest.mark.contract
│   └── harness/
│       └── __init__.py
└── support/             # Already created in Phase 0
```

Auto-marker conftest.py example:
```python
import pytest

def pytest_collection_modifyitems(items):
    for item in items:
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
```

Validation: Structure exists, pytest collection works

### Commit 5.2: Move Pure Logic Tests to tests/unit/
Identify and move tests that:
- Test pure functions with no I/O
- Use only in-memory data structures
- Don't need filesystem, network, or subprocess

Move incrementally, verify count preserved.

Validation: `pytest -m unit` works, test count preserved

### Commit 5.3: Move Boundary Tests to tests/integration/
Identify and move tests that:
- Test one real boundary (filesystem, subprocess, etc.)
- Use tmp_path or real processes
- Verify I/O behavior

Move incrementally, verify count preserved.

Validation: `pytest -m integration` works, test count preserved

### Commit 5.4: Move Parity Tests to tests/contract/
Identify and move tests that:
- Verify parity between implementations
- Check drift between specs and implementations
- Contract/invariant checks

Move incrementally, verify count preserved.

Validation: `pytest -m contract` works, test count preserved

### Commit 5.5: Tag and Move Remaining Root Tests
For tests that don't fit cleanly:
- Add explicit markers
- Move to appropriate directory based on primary behavior
- Document any that span multiple categories

Validation: Test count preserved, no unmarked tests in root

### Commit 5.6: Update CI Configuration
If needed, update CI to use marker-based selection:
- Fast gate: `pytest -m "unit or (integration and not slow)"`
- Full gate: `pytest -m "not windows_only"`

Validation: CI passes

## Notes
- Run `pytest --collect-only | wc -l` before and after each batch
- Keep detailed log of what moved where
- Some tests may need refactoring to fit cleanly into categories

## Exit Criteria
- All 6 commits made atomically
- Test count preserved (570+ tests)
- `pytest -m unit` runs cleanly
- `pytest -m integration` runs cleanly
- `pytest -m contract` runs cleanly
- No test discovery regressions
