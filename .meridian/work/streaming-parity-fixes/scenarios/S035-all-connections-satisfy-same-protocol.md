# S035: All three connections satisfy the same Protocol

- **Source:** design/edge-cases.md E35 (defensive; keeps impls in sync as Protocol evolves)
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester
- **Status:** pending

## Given
`HarnessConnection[SpecT]` is composed from `HarnessLifecycle`, `HarnessSender`, and `HarnessReceiver` Protocols (or equivalent ABCs). The three concrete implementations are:
- `ClaudeConnection(HarnessConnection[ClaudeLaunchSpec])`
- `CodexConnection(HarnessConnection[CodexLaunchSpec])`
- `OpenCodeConnection(HarnessConnection[OpenCodeLaunchSpec])`

## When
`isinstance` checks are run against each Protocol for each concrete connection, and pyright is run against the module graph.

## Then
- `isinstance(ClaudeConnection(...), HarnessLifecycle) is True`
- `isinstance(ClaudeConnection(...), HarnessSender) is True`
- `isinstance(ClaudeConnection(...), HarnessReceiver) is True`
- Same for `CodexConnection` and `OpenCodeConnection`.
- Pyright reports zero errors when the three classes are declared; removing a required method from any impl triggers a pyright error.
- Adding a new method to the Protocol and forgetting to implement it in any impl triggers pyright errors in all three that omit it.

## Verification
- Parametrized unit test over the three concrete classes × three Protocol classes (9 assertions).
- Pyright step asserts zero errors on the connections package.
- Negative test: manually delete a method from `CodexConnection` in a scratch branch, run pyright, assert at least one error naming the method and `CodexConnection`.
- Protocol-evolution test: add a fake method to `HarnessLifecycle` in a fixture, run pyright on the three impls, assert three errors (one per impl).

## Result (filled by tester)
_pending_
