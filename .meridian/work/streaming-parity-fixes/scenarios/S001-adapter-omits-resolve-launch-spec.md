# S001: Adapter omits `resolve_launch_spec` override

- **Source:** design/edge-cases.md E1 + p1411 finding M2
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester
- **Status:** pending

## Given
A developer adds a new harness adapter class subclassing the shared base (`BaseSubprocessHarness`) or implementing `HarnessAdapter[SpecT]` Protocol but forgets to define `resolve_launch_spec`.

## When
The class is instantiated, or pyright runs against the module.

## Then
- Pyright reports that the class does not satisfy `HarnessAdapter[SpecT]` because `resolve_launch_spec` is unimplemented.
- Runtime instantiation raises `TypeError: Can't instantiate abstract class ... with abstract method resolve_launch_spec` (or equivalent Protocol conformance failure).
- No silent fallback to a generic `ResolvedLaunchSpec` occurs.

## Verification
- Write a pytest fixture class: `class NewHarness(BaseSubprocessHarness): ...` with no `resolve_launch_spec` override and no other differentiating fields.
- Assert `NewHarness()` raises `TypeError`.
- Run `uv run pyright` on the fixture file and assert the Protocol-unsatisfied error is present.

## Result (filled by tester)
_pending_
