# S005: New field on `ClaudeLaunchSpec`, projection forgets it

- **Source:** design/edge-cases.md E5 + p1411 H4
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester
- **Status:** pending

## Given
A new field is added to `ClaudeLaunchSpec`, but `project_claude.py` accounting is not updated.

## When
Projection drift helper runs at import.

## Then
- `_check_projection_drift(...)` raises `ImportError` with missing/stale sets.
- Failure occurs at import time before any spawn runs.
- Guard behavior remains active under optimized Python mode.

## Verification
- Unit tests call `_check_projection_drift` directly with synthetic spec classes.
- Assert happy path, missing-field, and stale-field cases.
- No monkey-patching of `model_fields`.

## Result (filled by tester)
_pending_
