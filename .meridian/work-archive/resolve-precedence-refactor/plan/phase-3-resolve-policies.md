# Phase 3: Refactor `resolve_policies()` Core Resolution Logic

## Scope

Refactor `resolve_policies()` in `resolve.py` to:
1. Accept a `layers` tuple instead of a pre-merged `overrides` parameter
2. Replace the ad-hoc if/elif model/harness resolution with standard first-non-None via `resolve(*layers)`
3. Add harness fallback derivation (derive from model when no layer specifies harness)
4. Add `resolve_final_model()` for harness-specific model defaults
5. Add `validate_harness_model_compat()` for post-resolution validation
6. Move agent resolution into the layer stack (use `agent` from resolved layers)

This is the highest-risk phase. The existing ad-hoc logic (lines 199-256 of resolve.py) is replaced entirely.

## Files to Modify

### `src/meridian/lib/launch/resolve.py`

#### 1. Change `resolve_policies()` signature

Current:
```python
def resolve_policies(
    *,
    repo_root: Path,
    overrides: RuntimeOverrides,
    requested_agent: str | None,
    config: MeridianConfig,
    harness_registry: HarnessRegistry,
    configured_default_agent: str | None = None,
    builtin_default_agent: str = "",
    configured_default_harness: str = "claude",
    skills_readonly: bool = True,
) -> ResolvedPolicies:
```

New:
```python
def resolve_policies(
    *,
    repo_root: Path,
    layers: tuple[RuntimeOverrides, ...],
    config: MeridianConfig,
    harness_registry: HarnessRegistry,
    builtin_default_agent: str = "",
    configured_default_harness: str = "claude",
    skills_readonly: bool = True,
) -> ResolvedPolicies:
```

Removed parameters:
- `overrides` → replaced by `layers` (callers pass the full tuple)
- `requested_agent` → comes from `layers` via first-non-None on `agent` field
- `configured_default_agent` → comes from config layer in `layers` (which now has `agent` field)

#### 2. Replace body — agent resolution from layers

```python
# Step 1: Resolve agent from layers (without profile layer, since profile depends on agent)
resolved_pre_profile = resolve(*layers)
agent_name = resolved_pre_profile.agent or builtin_default_agent

# Step 2: Load profile
profile, profile_warning = resolve_agent_profile_with_builtin_fallback(
    repo_root=repo_root,
    requested_agent=agent_name if agent_name != builtin_default_agent else None,
    configured_default=agent_name,
    builtin_default=builtin_default_agent,
)
```

Wait — there's a subtlety. The `layers` tuple passed to `resolve_policies()` shouldn't include the profile layer yet, because the profile depends on the resolved agent. The caller builds `layers = (cli, env, config)`, passes it in, and `resolve_policies()` internally:
1. Resolves agent from those layers
2. Loads the profile
3. Inserts profile overrides into the layer stack at the correct position
4. Resolves all remaining fields

The caller needs to tell `resolve_policies()` where to insert the profile layer. Since the precedence is always `cli > env > profile > config`, the profile goes at index 2 (between env and config) when there are 3 pre-profile layers (cli, env, config). But the caller might pass layers differently.

**Simpler approach**: The caller passes `layers` WITHOUT the profile. `resolve_policies()` resolves agent, loads profile, and constructs the full layer tuple internally:

```python
def resolve_policies(
    *,
    repo_root: Path,
    layers: tuple[RuntimeOverrides, ...],  # cli, env, config — NO profile
    config: MeridianConfig,
    harness_registry: HarnessRegistry,
    builtin_default_agent: str = "",
    configured_default_harness: str = "claude",
    skills_readonly: bool = True,
) -> ResolvedPolicies:
    # Step 1: Resolve agent from pre-profile layers
    pre_profile_resolved = resolve(*layers)
    agent_name = pre_profile_resolved.agent or builtin_default_agent
    
    # Step 2: Load profile
    profile, profile_warning = resolve_agent_profile_with_builtin_fallback(
        repo_root=repo_root,
        requested_agent=agent_name if pre_profile_resolved.agent else None,
        configured_default=agent_name if not pre_profile_resolved.agent else "",
        builtin_default=builtin_default_agent,
    )
    profile_overrides = RuntimeOverrides.from_agent_profile(profile)
    
    # Step 3: Build full layer stack (cli, env, profile, config)
    # Profile inserts before config layer. Caller's layers are (cli, env, config).
    # Insert profile between env and config = before the last layer.
    if len(layers) >= 2:
        full_layers = (*layers[:-1], profile_overrides, layers[-1])
    else:
        full_layers = (*layers, profile_overrides)
    
    # Step 4: Resolve ALL fields via standard merge
    resolved = resolve(*full_layers)
    ...
```

**Problem**: This assumes the caller's last layer is always config. That's fragile. Better: require the caller to pass config separately (it's already a parameter), and have `resolve_policies()` own the full layer construction.

**Final approach** — keep `layers` as the non-config, non-profile layers (cli + env), and let `resolve_policies()` build the stack:

```python
def resolve_policies(
    *,
    repo_root: Path,
    layers: tuple[RuntimeOverrides, ...],  # CLI + ENV overrides (highest precedence)
    config_overrides: RuntimeOverrides,     # config layer (lowest precedence)
    config: MeridianConfig,
    harness_registry: HarnessRegistry,
    builtin_default_agent: str = "",
    configured_default_harness: str = "claude",
    skills_readonly: bool = True,
) -> ResolvedPolicies:
```

This is clearest. The caller passes:
- `layers` = `(cli_overrides, env_overrides)` — the layers above profile
- `config_overrides` = config layer — goes below profile
- `resolve_policies()` builds `(cli, env, profile, config)` internally

#### 3. Replace model/harness resolution body

Delete lines 199-256 (the ad-hoc if/elif). Replace with:

```python
    # Step 4: Resolve ALL fields via standard first-non-None merge
    resolved = resolve(*full_layers)  # full_layers = (cli, env, profile, config)
    
    # Step 5: Harness fallback — derive from model only if no layer set harness
    if resolved.harness:
        harness_id = HarnessId(resolved.harness)
    elif resolved.model:
        harness_id = derive_harness_from_model(resolved.model, repo_root=repo_root)
    else:
        harness_id = HarnessId(configured_default_harness or "claude")
    
    # Step 6: Get adapter (validates harness exists)
    try:
        adapter = harness_registry.get_subprocess_harness(harness_id)
    except (KeyError, TypeError) as exc:
        supported = ", ".join(str(h) for h in harness_registry.ids())
        raise ValueError(
            f"Unknown or unsupported harness '{harness_id}'. Available: {supported}"
        ) from exc
    
    # Step 7: Resolve final model (harness-specific defaults)
    final_model = resolve_final_model(
        layer_model=resolved.model,
        harness_id=harness_id,
        config=config,
        repo_root=repo_root,
    )
    
    # Step 8: Validate harness-model compatibility (if both independently specified)
    if final_model and resolved.harness and resolved.model:
        validate_harness_model_compat(harness_id, final_model, harness_registry, repo_root)
```

#### 4. Add new helper functions

**`derive_harness_from_model()`** — extracts harness routing from model name:
```python
def derive_harness_from_model(model: str, *, repo_root: Path) -> HarnessId:
    """Derive harness from model when no layer specifies harness."""
    try:
        resolved = resolve_model(model, repo_root=repo_root)
        return resolved.harness
    except ValueError:
        decision = route_model(model, mode="harness", repo_root=repo_root)
        return decision.harness_id
```

**`resolve_final_model()`** — applies harness-specific and global model defaults:
```python
def resolve_final_model(
    *,
    layer_model: str | None,
    harness_id: HarnessId,
    config: MeridianConfig,
    repo_root: Path,
) -> str:
    """Resolve final model string after harness is known."""
    if layer_model:
        try:
            catalog_entry = resolve_model(layer_model, repo_root=repo_root)
            return str(catalog_entry.model_id)
        except ValueError:
            return layer_model
    
    harness_default = config.default_model_for_harness(str(harness_id))
    if harness_default:
        return harness_default
    if config.default_model:
        return config.default_model
    return ""
```

**`validate_harness_model_compat()`** — post-resolution compatibility check:
```python
def validate_harness_model_compat(
    harness_id: HarnessId,
    model: str,
    harness_registry: HarnessRegistry,
    repo_root: Path,
) -> None:
    """Validate that harness and model are compatible. Raises ValueError if not."""
    resolve_harness(
        model=ModelId(model),
        harness_override=str(harness_id),
        harness_registry=harness_registry,
        repo_root=repo_root,
    )
```

#### 5. Return `ResolvedPolicies` and profile overrides

The function also needs to return the profile overrides (or the full resolved overrides) so the caller can use them for effort/sandbox/approval/etc. Two options:

**Option A**: Expand `ResolvedPolicies` to include resolved overrides.
**Option B**: Return the resolved overrides alongside `ResolvedPolicies`.

**Choose Option A** — add `resolved_overrides: RuntimeOverrides` to `ResolvedPolicies`:
```python
@dataclass(frozen=True)
class ResolvedPolicies:
    profile: AgentProfile | None
    model: str
    harness: HarnessId
    adapter: SubprocessHarness
    resolved_skills: ResolvedSkills
    resolved_overrides: RuntimeOverrides  # NEW — full merged overrides
    warning: str | None = None
```

This eliminates the caller's need to do its own `resolve()` call.

## Dependencies

- Requires Phase 1 (`agent` field on `RuntimeOverrides`)

## Interface Contract

New `resolve_policies()` signature:
```python
def resolve_policies(
    *,
    repo_root: Path,
    layers: tuple[RuntimeOverrides, ...],
    config_overrides: RuntimeOverrides,
    config: MeridianConfig,
    harness_registry: HarnessRegistry,
    builtin_default_agent: str = "",
    configured_default_harness: str = "claude",
    skills_readonly: bool = True,
) -> ResolvedPolicies:
```

`ResolvedPolicies` now includes `resolved_overrides: RuntimeOverrides` with the fully merged overrides (cli > env > profile > config).

New helper functions: `derive_harness_from_model()`, `resolve_final_model()`, `validate_harness_model_compat()`.

## Verification Criteria

- [ ] `uv run pyright` passes (0 errors)
- [ ] `uv run ruff check .` passes
- [ ] `uv run pytest-llm` passes
- [ ] The old callers will NOT compile until they're updated (Phase 4/5) — this is expected. Verify pyright catches the signature mismatch.

## Out of Scope

- Caller updates (Phase 4, Phase 5)
- CLI changes (Phase 6)
- Approval "default" sentinel fix (deferred per D6)

## Agent Staffing

- 1 coder (default model)
- 3 reviewers: 1 on default model (correctness), 1 on a second model (design alignment with design/resolve-pipeline.md), 1 on a third model (edge case analysis — model alias timing, empty strings, None vs "")
- 1 verifier
