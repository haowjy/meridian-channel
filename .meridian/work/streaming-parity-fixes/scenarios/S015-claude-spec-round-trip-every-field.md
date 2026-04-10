# S015: Claude spec round-trip with every field populated

- **Source:** design/edge-cases.md E15 + p1411 M3/H2
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester
- **Status:** pending

## Given
A `ClaudeLaunchSpec` fixture with every relevant field populated.

## When
Projected through subprocess and streaming Claude projections.

## Then
- Canonical ordering is preserved.
- Arg tails are byte-equal across transports.
- Permission flags are deduped/merged exactly once.

## Verification
- Parametrized table maps each `ClaudeLaunchSpec` field to exact expected representation:
  flag pair, merged-tail effect, or explicit delegation target.
- Tests assert table coverage for all `model_fields`.
- Parity assertion checks subprocess tail equals streaming tail.

## Result (filled by tester)
_pending_
