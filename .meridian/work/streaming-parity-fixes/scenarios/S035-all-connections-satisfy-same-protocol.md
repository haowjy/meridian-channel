# S035: All connections satisfy the same `HarnessConnection` surface

- **Source:** design/edge-cases.md E35
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester
- **Status:** pending

## Given
v2 uses a single `HarnessConnection[SpecT]` ABC (facet protocols removed). Concrete classes:

- `ClaudeConnection(HarnessConnection[ClaudeLaunchSpec])`
- `CodexConnection(HarnessConnection[CodexLaunchSpec])`
- `OpenCodeConnection(HarnessConnection[OpenCodeLaunchSpec])`

## When
Pyright and runtime inheritance checks execute.

## Then
- All three are subclasses of `HarnessConnection`.
- All abstract methods are implemented.
- Removing any required method from one implementation produces pyright error and runtime instantiation failure.

## Verification
- Parametrized `issubclass` checks across concrete classes.
- Pyright check across connections package.
- Negative scratch test removing one abstract method confirms failure path.

## Result (filled by tester)
_pending_
