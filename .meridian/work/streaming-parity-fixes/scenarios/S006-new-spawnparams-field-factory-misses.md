# S006: New field on `SpawnParams`, factory doesn't map it

- **Source:** design/edge-cases.md E6 + p1411 finding L1 (assert under -O)
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester
- **Status:** pending

## Given
A developer adds `bar: str | None = None` to `SpawnParams` (the transport-neutral run parameter bundle) but does not update `_SPEC_HANDLED_FIELDS` / `_SPEC_DELEGATED_FIELDS` in `launch_spec.py` and does not update any adapter's `resolve_launch_spec`.

## When
`launch_spec.py` is imported at application startup.

## Then
- `ImportError` is raised naming `bar` as an unmapped field and listing the adapter implementations that must be updated.
- Error fires whether running under `python` or `python -O` (uses `ImportError`, not `assert`).
- No field silently disappears between `SpawnParams` and the resolved spec.

## Verification
- Fixture that temporarily adds a field to `SpawnParams.model_fields` and re-imports `launch_spec`.
- Assert `ImportError` with the expected message.
- Run `PYTHONOPTIMIZE=1 uv run pytest-llm tests/unit/harness/test_spec_field_guards.py` to confirm `-O` safety.
- Grep `src/meridian/lib/harness/launch_spec.py` for `assert ` — zero results (the v1 assert on L1 must be removed).

## Result (filled by tester)
_pending_
