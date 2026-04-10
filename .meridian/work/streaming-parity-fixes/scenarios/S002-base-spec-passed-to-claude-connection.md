# S002: Base `ResolvedLaunchSpec` passed to Claude dispatch

- **Source:** design/edge-cases.md E2 + p1411 M1
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @unit-tester
- **Status:** pending

## Given
A caller passes `ResolvedLaunchSpec(...)` where Claude dispatch expects `ClaudeLaunchSpec`.

## When
Dispatch path is executed through `SpawnManager.start_spawn`/`dispatch_start`.

## Then
- Pyright rejects the call site without ignore.
- Runtime dispatch guard raises `TypeError` at boundary:
  `isinstance(spec, bundle.spec_cls)` fails before `connection.start(...)`.
- Connection implementations do not contain behavior-switching `isinstance` branches.

## Verification
- Runtime test with `# type: ignore[arg-type]` triggers boundary `TypeError`.
- Static test without ignore shows pyright mismatch.
- Grep audit confirms runtime guard lives at dispatch boundary.

## Result (filled by tester)
_pending_
