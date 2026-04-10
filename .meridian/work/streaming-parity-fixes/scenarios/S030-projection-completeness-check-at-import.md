# S030: Projection completeness check runs at import

- **Source:** design/edge-cases.md E30 + p1411 H4
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester
- **Status:** pending

## Given
Projection modules use `_check_projection_drift(...)` at module import:

- `project_claude.py`
- `project_codex_subprocess.py`
- `project_codex_streaming.py`
- `project_opencode_subprocess.py`
- `project_opencode_streaming.py`

## When
Modules are imported.

## Then
- Drift raises `ImportError` immediately.
- Missing and stale directions are both reported.
- Guard behavior survives optimized runtime.

## Verification
- Unit tests exercise `_check_projection_drift` helper with synthetic spec classes.
- Import smoke confirms real modules execute guard on import.
- Meta assertion: `rg "_PROJECTED_FIELDS" src/meridian/lib/harness/projections/` returns exactly 5 matches (one per projection module listed above).

## Result (filled by tester)
_pending_
