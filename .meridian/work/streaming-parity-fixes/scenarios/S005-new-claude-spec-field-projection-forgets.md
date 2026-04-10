# S005: New field on `ClaudeLaunchSpec`, projection forgets it

- **Source:** design/edge-cases.md E5 + p1411 finding H4 (D15 missing)
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester
- **Status:** pending

## Given
A developer adds a new field `foo: str | None = None` to `ClaudeLaunchSpec` but does not update `projections/claude.py::_PROJECTED_FIELDS` and does not handle the new field in `project_claude_spec_to_cli_args`.

## When
The projection module is imported (which happens at application startup via the adapter module).

## Then
- `ImportError` is raised with a message naming `foo` as an unprojected field and pointing at `projections/claude.py` as the file to update.
- The error surfaces **before** any spawn runs — no silent dropping of `foo` on the wire.
- No `assert` is used (so the guard still fires under `python -O`).

## Verification
- Write a pytest fixture that monkey-patches `ClaudeLaunchSpec` to include an extra field via `model_fields` snapshot, then re-imports the projection module.
- Assert `ImportError` with the expected message.
- Alternatively: grep for `assert` in `projections/claude.py` and confirm it does not exist.
- Run `PYTHONOPTIMIZE=1 uv run pyright` and `PYTHONOPTIMIZE=1 uv run pytest-llm tests/unit/harness/test_projection_guards.py` to confirm the guard still fires.

## Result (filled by tester)
_pending_
