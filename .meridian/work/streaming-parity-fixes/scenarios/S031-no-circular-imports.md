# S031: No circular imports

- **Source:** design/edge-cases.md E31
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @verifier
- **Status:** pending

## Given
Current typed module DAG:

- `harness/launch_types.py`
- `harness/adapter.py`
- `harness/launch_spec.py`
- `harness/projections/project_claude.py`
- `harness/projections/project_codex_subprocess.py`
- `harness/projections/project_codex_streaming.py`
- `harness/projections/project_opencode_subprocess.py`
- `harness/projections/project_opencode_streaming.py`
- `harness/connections/*.py`

## When
Modules are imported in fresh interpreters and pyright runs.

## Then
- Imports succeed without cycle errors.
- pyright resolves types with no cycle-induced failures.

## Verification
- Scripted per-module import smoke test.
- `uv run pyright` full-tree check.

## Result (filled by tester)
_pending_
