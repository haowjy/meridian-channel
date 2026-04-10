# S048: Cancel vs completion race — exactly one terminal status persisted

- **Source:** design/edge-cases.md E41 + decisions.md K8 (revision round 3)
- **Added by:** @design-orchestrator (revision round 3)
- **Tester:** @unit-tester
- **Status:** pending

## Given
A spawn whose harness finishes naturally (emits a `completed` event) at roughly the same time the runner receives a cancellation intent. The ordering is non-deterministic — the test deliberately exercises both orderings.

## When
- Case A: `send_cancel()` resolves before the `completed` event reaches the spawn store.
- Case B: the `completed` event reaches the spawn store before `send_cancel()` resolves.

## Then
- Exactly one terminal status is persisted for the spawn id.
- The first terminal write wins. The second write is dropped by the spawn store's atomic tmp+rename behavior, or explicitly rejected by the spawn store's terminal-status idempotency check.
- No `AssertionError` or `ValueError` in the runner, regardless of ordering.
- The spawn event log contains both the cancel event and the completed event (both are audit-visible), but only one terminal status transition.

## Verification
- Unit test: drive a fake connection that emits `completed` on a controlled `asyncio.Event`; trigger `send_cancel` in parallel; assert terminal status consistency.
- Run the test with both orderings (cancel-first, completion-first) by parameterizing which event fires first.
- Assert `meridian spawn show` reports exactly one terminal status and the first-wins ordering.
- Assert the spawn store's terminal-status write path is idempotent: a second write with a different status is a no-op, not an exception.

## Result (filled by tester)
_pending_
