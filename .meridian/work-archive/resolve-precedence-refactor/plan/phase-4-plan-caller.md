# Phase 4: Rewire `plan.py` (Primary Launch Caller)

## Scope

Simplify `resolve_primary_launch_plan()` in `plan.py` to use the new `resolve_policies()` signature. The current dual-resolution pattern (pre_resolved without config, then full resolved separately) collapses into a single call.

## Files to Modify

### `src/meridian/lib/launch/plan.py`

#### Current code (lines 163-180):
```python
cli_overrides = RuntimeOverrides.from_launch_request(request)
env_overrides = RuntimeOverrides.from_env()
config_overrides = RuntimeOverrides.from_config(resolved_config)
pre_resolved = resolve(cli_overrides, env_overrides)

policies: ResolvedPolicies = resolve_policies(
    repo_root=resolved_root,
    overrides=pre_resolved,
    requested_agent=request.agent,
    config=resolved_config,
    harness_registry=harness_registry,
    configured_default_agent=resolved_config.primary_agent,
    builtin_default_agent="__meridian-orchestrator",
    configured_default_harness=resolved_config.primary.harness or "claude",
    skills_readonly=True,
)
profile = policies.profile
profile_overrides = RuntimeOverrides.from_agent_profile(profile)
resolved = resolve(cli_overrides, env_overrides, profile_overrides, config_overrides)
```

#### New code:
```python
cli_overrides = RuntimeOverrides.from_launch_request(request)
env_overrides = RuntimeOverrides.from_env()
config_overrides = RuntimeOverrides.from_config(resolved_config)

policies: ResolvedPolicies = resolve_policies(
    repo_root=resolved_root,
    layers=(cli_overrides, env_overrides),
    config_overrides=config_overrides,
    config=resolved_config,
    harness_registry=harness_registry,
    builtin_default_agent="__meridian-orchestrator",
    configured_default_harness=resolved_config.primary.harness or "claude",
    skills_readonly=True,
)
profile = policies.profile
resolved = policies.resolved_overrides  # No more separate resolve() call
```

#### Downstream changes in the same function:

- `resolved.effort`, `resolved.sandbox`, `resolved.approval` etc. now come from `policies.resolved_overrides` — same field access, different source
- `model = ModelId(policies.model) if policies.model else None` — unchanged
- Remove the `resolve` import if no longer needed (it's still used by `resolve_policies` internally, but `plan.py` may no longer call it directly)

#### Update imports:

Remove `resolve` from the import if `plan.py` no longer calls it:
```python
from meridian.lib.core.overrides import RuntimeOverrides  # remove 'resolve'
```

## Dependencies

- Requires Phase 3 (new `resolve_policies()` signature and `resolved_overrides` on `ResolvedPolicies`)

## Interface Contract

`resolve_primary_launch_plan()` signature is unchanged — this is an internal refactor. The `ResolvedPrimaryLaunchPlan` output should be identical for the same inputs.

## Verification Criteria

- [ ] `uv run pyright` passes (0 errors)
- [ ] `uv run ruff check .` passes
- [ ] `uv run pytest-llm` passes
- [ ] Smoke test: `uv run meridian --dry-run` produces same output as before the refactor
- [ ] Smoke test: `uv run meridian claude --dry-run -m sonnet` resolves correctly

## Agent Staffing

- 1 coder (default model)
- 2 reviewers: 1 on default model (correctness + regression), 1 on a different model (design alignment)
- 1 verifier
