# S002: Base `ResolvedLaunchSpec` passed to `ClaudeConnection.start`

- **Source:** design/edge-cases.md E2 + p1411 finding M1
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester
- **Status:** pending

## Given
A caller (legacy code path, test, or mistaken future edit) constructs a base `ResolvedLaunchSpec(prompt="hi", ...)` instance and attempts to pass it to `ClaudeConnection.start(config, spec)`.

## When
Pyright runs over the call site OR the call is made at runtime.

## Then
- Pyright rejects the call with "argument of type ResolvedLaunchSpec is not assignable to parameter of type ClaudeLaunchSpec".
- If the call happens at runtime despite a type-ignore, a runtime guard at the top of `ClaudeConnection.start` raises `TypeError: ClaudeConnection.start requires ClaudeLaunchSpec, got ResolvedLaunchSpec`.
- No silent fallback to generic spec behavior. No isinstance branch that quietly skips every Claude-specific field.

## Verification
- Author a pytest module that constructs a base `ResolvedLaunchSpec` and calls `ClaudeConnection.start` with `# type: ignore[arg-type]`.
- Assert the call raises `TypeError` at runtime.
- Author a second test file without the ignore and assert `uv run pyright` reports the type mismatch.

## Result (filled by tester)
_pending_
