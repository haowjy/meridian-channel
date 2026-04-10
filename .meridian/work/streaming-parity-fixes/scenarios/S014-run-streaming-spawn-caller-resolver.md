# S014: `run_streaming_spawn` with caller-supplied resolver

- **Source:** design/edge-cases.md E14 + p1411 findings H3 + H1
- **Added by:** @design-orchestrator (design phase)
- **Tester:** @smoke-tester (+ @unit-tester)
- **Status:** pending

## Given
An external caller invokes `run_streaming_spawn(config, params, perms=my_resolver, ...)` where `my_resolver.config.sandbox = "read-only"` and `my_resolver.config.approval = "auto"`. Harness is Codex.

## When
The streaming runner routes through the adapter factory to produce a `CodexLaunchSpec`.

## Then
- `my_resolver` reaches `CodexAdapter.resolve_launch_spec` unchanged (no cast-to-None, no silent swap to a default resolver).
- The produced `CodexLaunchSpec.permission_resolver is my_resolver`.
- The Codex app-server projection reads `my_resolver.config.sandbox` and emits `-c sandbox_mode="read-only"` on the wire.
- Grep confirms the v1 `cast("PermissionResolver", None)` in `streaming_runner.py` is gone.

## Verification
- Unit test: call `run_streaming_spawn` with a synthetic resolver and a stubbed `CodexConnection.start` that captures the spec; assert `spec.permission_resolver is my_resolver`.
- Smoke test: end-to-end streaming Codex spawn with a caller-supplied resolver asserting read-only sandbox enforcement.
- `rg "cast\\(.*PermissionResolver" src/meridian/lib/launch/streaming_runner.py` returns zero.

## Result (filled by tester)
_pending_
