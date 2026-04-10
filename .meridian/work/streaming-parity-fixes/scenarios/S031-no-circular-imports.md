# S031: No circular imports

- **Source:** design/edge-cases.md E31 (defensive; generics can introduce subtle cycles)
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @verifier
- **Status:** pending

## Given
The v2 module graph:
- `launch_spec.py` (defines `ResolvedLaunchSpec` and subtypes)
- `adapter.py` (defines `HarnessAdapter[SpecT]`, `BaseSubprocessHarness[SpecT]`, `HarnessBundle`)
- `projections/claude.py`, `projections/codex.py`, `projections/opencode.py`
- `connections/base.py`, `connections/claude_ws.py`, `connections/codex_ws.py`, `connections/opencode_http.py`
- `launch/runner.py`, `launch/streaming_runner.py`

## When
Each module is imported individually as the first import in a fresh Python interpreter.

## Then
- Every module imports cleanly without `ImportError` caused by circular dependencies.
- `import meridian.lib.harness.launch_spec` succeeds standalone.
- `import meridian.lib.harness.adapter` succeeds standalone.
- `import meridian.lib.launch.streaming_runner` succeeds standalone.
- Pyright runs over the whole tree without type-resolution cycles.

## Verification
- Script: iterate over the module list and `python -c "import <module>"` for each; assert all succeed.
- `uv run pyright` over the full tree returns zero errors.
- If a cycle exists, document the forward-reference fix (e.g., `from __future__ import annotations` or `TYPE_CHECKING` import) in the decision log and the affected module.
- Re-run after every structural refactor.

## Result (filled by tester)
_pending_
