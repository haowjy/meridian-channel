# Phase 5: Rewire `prepare.py` (Spawn Caller)

## Scope

Update `build_create_payload()` in `prepare.py` to use the new `resolve_policies()` signature. Same pattern as Phase 4, but uses `from_spawn_config()` for the config layer instead of `from_config()`.

## Files to Modify

### `src/meridian/lib/ops/spawn/prepare.py`

#### Current code (lines 198-216):
```python
cli_overrides = RuntimeOverrides.from_spawn_input(payload)
env_overrides = RuntimeOverrides.from_env()
config_overrides = RuntimeOverrides.from_config(runtime_view.config)
pre_resolved = resolve(cli_overrides, env_overrides)

policies = resolve_policies(
    repo_root=runtime_view.repo_root,
    overrides=pre_resolved,
    requested_agent=payload.agent,
    config=runtime_view.config,
    harness_registry=runtime_view.harness_registry,
    configured_default_agent=runtime_view.config.default_agent,
    builtin_default_agent="__meridian-subagent",
    configured_default_harness=runtime_view.config.default_harness,
    skills_readonly=payload.dry_run,
)
profile = policies.profile
profile_overrides = RuntimeOverrides.from_agent_profile(profile)
resolved = resolve(cli_overrides, env_overrides, profile_overrides, config_overrides)
```

#### New code:
```python
cli_overrides = RuntimeOverrides.from_spawn_input(payload)
env_overrides = RuntimeOverrides.from_env()
config_overrides = RuntimeOverrides.from_spawn_config(runtime_view.config)

policies = resolve_policies(
    repo_root=runtime_view.repo_root,
    layers=(cli_overrides, env_overrides),
    config_overrides=config_overrides,
    config=runtime_view.config,
    harness_registry=runtime_view.harness_registry,
    builtin_default_agent="__meridian-subagent",
    configured_default_harness=runtime_view.config.default_harness,
    skills_readonly=payload.dry_run,
)
profile = policies.profile
resolved = policies.resolved_overrides  # No more separate resolve() call
```

Key difference from Phase 4: uses `from_spawn_config()` (Phase 2) instead of `from_config()`. This reads `config.default_*` instead of `config.primary.*`.

#### Downstream changes:

- `resolved.effort`, `resolved.sandbox`, `resolved.approval`, `resolved.timeout`, `resolved.autocompact` now come from `policies.resolved_overrides`
- Remove the separate `resolve()` call and its import if no longer needed
- The `payload.agent` no longer needs to be passed separately — it's in `cli_overrides.agent` from `from_spawn_input()`

#### Update imports:

Remove `resolve` from the import if `prepare.py` no longer calls it directly:
```python
from meridian.lib.core.overrides import RuntimeOverrides  # remove 'resolve'
```

Also remove `RuntimeOverrides.from_config` import reference if only `from_spawn_config` is used.

## Dependencies

- Requires Phase 2 (`from_spawn_config()` factory method)
- Requires Phase 3 (new `resolve_policies()` signature)

## Interface Contract

`build_create_payload()` signature and return type (`PreparedSpawnPlan`) are unchanged — internal refactor only. Same inputs should produce same outputs.

## Verification Criteria

- [ ] `uv run pyright` passes (0 errors)
- [ ] `uv run ruff check .` passes
- [ ] `uv run pytest-llm` passes
- [ ] Smoke test: `uv run meridian spawn --dry-run -p "test" -m sonnet` resolves correctly
- [ ] Smoke test: `uv run meridian spawn --dry-run -p "test" -a __meridian-subagent` resolves agent from CLI

## Agent Staffing

- 1 coder (default model)
- 2 reviewers: 1 on default model (correctness + regression), 1 on a different model (design alignment, verify spawn vs primary config distinction)
- 1 verifier
