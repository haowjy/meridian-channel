# S027: `python -O` strips nothing meaningful

- **Source:** design/edge-cases.md E27 + p1411 finding L1
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @verifier
- **Status:** pending

## Given
The v2 design replaces every `assert` used for completeness checking with `raise ImportError(...)`. The running environment sets `PYTHONOPTIMIZE=1` (equivalent to `python -O`), which strips assertions.

## When
The full test suite runs under `PYTHONOPTIMIZE=1 uv run pytest-llm`.

## Then
- All completeness guard scenarios (S005, S006, S030) still fire correctly — because they use `ImportError`, not `assert`.
- Total pass/fail counts match a non-optimized run.
- No silent regression where a guard stops working because `-O` stripped the `assert`.
- `rg "assert " src/meridian/lib/harness/launch_spec.py` and `rg "assert " src/meridian/lib/harness/projections/` return only non-guard asserts (e.g., loop invariants that are OK to strip), and ideally zero in guard-related files.

## Verification
- Run the full suite twice: once with normal `uv run pytest-llm`, once with `PYTHONOPTIMIZE=1 uv run pytest-llm`.
- Compare the `pass/fail/skip` counts — must match.
- Specifically check S005, S006, S030 scenarios — they must fail (as expected) under both modes when the guard is intentionally broken.
- Grep `src/meridian/lib/harness/launch_spec.py` for `assert ` — there must be zero uses for completeness checking.
- Grep `src/meridian/lib/harness/projections/` for `assert ` — same.

## Result (filled by tester)
_pending_
