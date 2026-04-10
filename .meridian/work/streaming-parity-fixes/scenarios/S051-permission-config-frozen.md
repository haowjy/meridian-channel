# S051: `PermissionConfig` is frozen after construction

- **Source:** design/edge-cases.md E43 + decisions.md K7 (revision round 3)
- **Added by:** @design-orchestrator (revision round 3)
- **Tester:** @unit-tester
- **Status:** pending

## Given
A `PermissionConfig(sandbox="read-only", approval="default")` instance held inside a `PermissionResolver` that is in turn held inside a `ResolvedLaunchSpec`.

## When
Downstream code attempts to mutate the config:

- `config.sandbox = "yolo"`
- `setattr(config, "sandbox", "yolo")`
- `object.__setattr__(config, "sandbox", "yolo")` (also should fail on frozen Pydantic)

## Then
- Each mutation attempt raises `ValidationError` / `TypeError` per Pydantic v2 frozen-model semantics.
- The original config value is preserved — no silent mutation.
- `PreflightResult.extra_env` wrapped in `MappingProxyType` rejects mutation attempts with `TypeError`.
- `LaunchContext.env` and `LaunchContext.env_overrides` also wrapped in `MappingProxyType` and reject mutation.

## Verification
- Unit test: construct `PermissionConfig`, assert each mutation attempt above raises.
- Unit test: construct `PreflightResult.build(expanded_passthrough_args=(), extra_env={"K":"V"})`, assert `result.extra_env["K2"] = "V2"` raises `TypeError`.
- Unit test: `LaunchContext.env["FOO"] = "bar"` raises.
- Positive test: reading the frozen values still works (`config.sandbox == "read-only"`).
- Cross-check: grep for any `config.sandbox =` assignment in the runtime codebase — there should be zero.

## Result (filled by tester)
_pending_
