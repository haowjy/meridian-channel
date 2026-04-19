# Phase 6: CLI Cleanup

## Objective
Split cli/main.py into focused modules for maintainability.

## Commits (Execute in Order)

### Commit 6.1: Extract cli/bootstrap.py
Create `src/meridian/cli/bootstrap.py`:
- Startup validation logic
- Environment setup
- Configuration initialization

In `main.py`:
- Import from bootstrap.py
- Call bootstrap functions

Validation: Existing tests pass

### Commit 6.2: Extract cli/mars_passthrough.py
Create `src/meridian/cli/mars_passthrough.py`:
- Mars subprocess forwarding logic
- Mars command routing

In `main.py`:
- Import from mars_passthrough.py
- Route mars commands appropriately

Validation: Existing tests pass

### Commit 6.3: Extract cli/primary_launch.py
Create `src/meridian/cli/primary_launch.py`:
- Primary session launch policy
- Launch mode determination
- Primary process orchestration

In `main.py`:
- Import from primary_launch.py
- Delegate primary launch logic

Validation: Existing tests pass

### Commit 6.4: Slim Down main.py
Update `src/meridian/cli/main.py`:
- Keep only argv parsing and command routing
- Delegate all logic to extracted modules
- Should be significantly shorter (~500 lines target)

Validation: All existing tests pass, main.py is cleaner

## Files to Touch
- Create: `src/meridian/cli/bootstrap.py`
- Create: `src/meridian/cli/mars_passthrough.py`
- Create: `src/meridian/cli/primary_launch.py`
- Modify: `src/meridian/cli/main.py`

## Exit Criteria
- All 4 commits made atomically
- Each commit passes pytest
- main.py is significantly smaller
- Clear separation of concerns
- All CLI functionality preserved
