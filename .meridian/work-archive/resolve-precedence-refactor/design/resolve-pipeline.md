# Resolve Pipeline: Detailed Design

## Current Flow (Buggy)

```
plan.py:
  cli_overrides = RuntimeOverrides.from_launch_request(request)
  env_overrides = RuntimeOverrides.from_env()
  config_overrides = RuntimeOverrides.from_config(config)
  pre_resolved = resolve(cli_overrides, env_overrides)       # <-- config excluded!
  
  policies = resolve_policies(overrides=pre_resolved, ...)   # <-- ad-hoc model/harness
  
  profile_overrides = RuntimeOverrides.from_agent_profile(profile)
  resolved = resolve(cli, env, profile, config)              # <-- used only for effort/etc.
```

Problems:
- `resolve_policies()` receives only CLI+ENV, never sees config model/harness
- Model/harness resolved via if/elif inside `resolve_policies()`, not via layer merge
- Harness locked in before config default model is even considered
- Two separate `resolve()` calls with different layer sets

## Target Flow

```
plan.py:
  cli_overrides = RuntimeOverrides.from_launch_request(request)
  env_overrides = RuntimeOverrides.from_env()
  config_overrides = RuntimeOverrides.from_config(config)  # primary path: config.primary.*
  
  # Step 1: Load profile (needs agent from layers — agent resolved first)
  agent = first_non_none(cli.agent, env.agent, config.agent) or builtin_default
  profile = load_agent_profile(agent, ...)
  profile_overrides = RuntimeOverrides.from_agent_profile(profile)
  
  # Step 2: Build layer tuple in precedence order
  layers = (cli_overrides, env_overrides, profile_overrides, config_overrides)
  
  # Step 3: Resolve ALL fields via standard merge (model, harness, effort, etc.)
  resolved = resolve(*layers)
  
  # Step 4: Harness fallback — derive from model only if no layer set harness
  if resolved.harness:
      harness_id = HarnessId(resolved.harness)
  elif resolved.model:
      harness_id = derive_harness_from_model(resolved.model, repo_root=repo_root)
  else:
      harness_id = HarnessId(config.default_harness or "claude")
  
  # Step 5: Validate harness-model compatibility
  validate_harness_model_compat(harness_id, resolved.model, harness_registry)
  
  # Step 6: Resolve final model (apply harness-specific defaults if no model set)
  final_model = resolve_final_model(
      layer_model=resolved.model,
      harness_id=harness_id,
      config=config,
      repo_root=repo_root,
  )
  
  # Step 7: Resolve adapter, skills, build ResolvedPolicies
  adapter = harness_registry.get_subprocess_harness(harness_id)
  ...
```

Note: `prepare.py` (spawn path) uses a different `from_config()` variant that reads
`config.default_*` instead of `config.primary.*`. See "Primary vs Spawn Config" below.

## Key Functions

### `resolve()` (overrides.py) — No change needed

```python
def resolve(*layers: RuntimeOverrides) -> RuntimeOverrides:
    """Merge layers with first-non-none precedence."""
    resolved: dict[str, object] = {}
    for field_name in RuntimeOverrides.model_fields:
        for layer in layers:
            value = getattr(layer, field_name)
            if value is not None:
                resolved[field_name] = value
                break
    return RuntimeOverrides.model_validate(resolved)
```

Already generic. Works for any field on RuntimeOverrides, including harness.

### Harness resolution — independent field, not derived from model

**Correction from user review**: Harness and model are independent fields. Both
resolve via standard first-non-None across layers. Harness derivation from model
is a **fallback** only when no layer specifies a harness at all.

```python
resolved = resolve(*layers)
# resolved.harness and resolved.model are independently resolved

if not resolved.harness and resolved.model:
    # No layer set harness — derive from model as fallback
    resolved_harness = derive_harness_from_model(resolved.model, repo_root=repo_root)
elif not resolved.harness:
    resolved_harness = HarnessId(default_harness or "claude")
else:
    resolved_harness = HarnessId(resolved.harness)

# Validate compatibility — error only if truly impossible
validate_harness_model_compat(resolved_harness, resolved.model, harness_registry)
```

This is simpler than the layer-aware scan. No special scanning logic needed —
`resolve()` already handles precedence correctly for all fields. The only addition
is the fallback derivation when harness is absent.

**Why this works**: `meridian spawn -a reviewer -m sonnet` where the profile has
`harness: opencode` resolves to `model=sonnet, harness=opencode`. That's correct —
opencode can run anthropic models. The combination is validated, not overridden.

**Why the layer-aware scan was wrong**: It assumed `-m sonnet` should override the
profile's harness. But the user only overrode the model, not the harness. The profile
author chose opencode for a reason — maybe they want multi-provider support. Respect it.

### `resolve_final_model()` (resolve.py) — New function

```python
def resolve_final_model(
    *,
    layer_model: str | None,
    harness_id: HarnessId,
    config: MeridianConfig,
    repo_root: Path,
) -> str:
    """Apply harness-specific and global model defaults after harness is known.
    
    Precedence:
    1. layer_model (already resolved from CLI > ENV > profile > config.primary.model)
    2. config.default_model_for_harness(harness_id)
    3. config.default_model
    4. "" (empty — adapter will use its own default)
    """
```

This replaces lines 233-248 of resolve.py.

### Updated `resolve_policies()` signature

```python
def resolve_policies(
    *,
    repo_root: Path,
    layers: tuple[RuntimeOverrides, ...],   # <-- replaces single 'overrides'
    profile: AgentProfile | None,           # <-- pre-loaded
    config: MeridianConfig,
    harness_registry: HarnessRegistry,
    configured_default_harness: str = "claude",
    skills_readonly: bool = True,
) -> ResolvedPolicies:
```

Or alternatively, keep the `overrides` parameter but require callers to pass the full merged result. The key change is that the caller controls the layer stack and `resolve_policies()` doesn't do its own ad-hoc resolution.

## RuntimeOverrides Changes

### Add `agent` field, remove `--harness` CLI flag

Remove the `--harness` flag from `meridian spawn` CLI. Harness is set via:
- Subcommand (`meridian codex`) → sets harness in `LaunchRequest`
- Profile `harness:` field → sets harness in `from_agent_profile()`
- Config `primary.harness` / `default_harness` → sets harness in `from_config()`

The `harness` field stays on `RuntimeOverrides` (profiles and config still set it). Only the CLI flag goes away.

```python
class RuntimeOverrides(BaseModel):
    model: str | None = None
    harness: str | None = None    # still used by profiles/config/subcommands
    agent: str | None = None      # <-- NEW
    effort: str | None = None
    sandbox: str | None = None
    approval: str | None = None
    autocompact: int | None = None
    timeout: float | None = None
```

Update factory methods:
- `from_launch_request()`: read `request.agent`
- `from_env()`: read `MERIDIAN_AGENT` env var
- `from_config()`: read `config.primary.agent`
- `from_agent_profile()`: no agent field (profile IS the agent, doesn't override itself)
- `from_spawn_input()`: read `payload.agent`

### Fix approval="default"

```python
@classmethod
def from_launch_request(cls, request: LaunchRequest) -> RuntimeOverrides:
    return cls(
        ...
        approval=request.approval if request.approval else None,  # <-- was != "default"
        ...
    )
```

Wait — this needs more thought. The CLI default for `--approval` is `"default"`. If the user doesn't pass `--approval`, the value is still `"default"`. We need to distinguish "user explicitly passed `--approval default`" from "user didn't pass `--approval` at all."

**Solution**: Change the CLI default for `--approval` from `"default"` to `None`. When `None`, it means "not specified." When `"default"`, it means explicitly requested. This is a CLI-layer change, not a resolve-layer change.

If changing the CLI default isn't feasible (backwards compat), keep the current behavior and document it as a known limitation. The `--approval default` use case is edge-case — users rarely want to explicitly reset to default.

## Derivation Order

Three phases, standard first-non-None for all fields:

```
Phase 1: Resolve agent, load profile
  - agent = first_non_none(cli.agent, env.agent, config.agent) or builtin
  - profile = load(agent)
  - profile_overrides = RuntimeOverrides.from_agent_profile(profile)
  - layers = (cli, env, profile, config)  -- in strict precedence order

Phase 2: Resolve all fields + harness fallback
  - resolved = resolve(*layers)  -- standard first-non-None for ALL fields
  - if resolved.harness: use it (from subcommand, profile, or config)
  - elif resolved.model: derive harness from model
  - else: config.default_harness
  - validate_harness_model_compat()

Phase 3: resolve_final_model(layer_model=resolved.model, harness_id, config)
  - If layer_model set: resolve alias, done
  - If not: config.default_model_for_harness(harness_id) || config.default_model || ""
```

This is simpler than layer-aware scanning because harness and model are independent:
- `meridian codex -m sonnet` → harness=codex (subcommand), model=sonnet → validate compat
- `-a reviewer -m sonnet` (profile: harness=opencode) → harness=opencode (profile), model=sonnet (CLI) → valid
- `-m sonnet` (no harness anywhere) → derive claude from model → valid
- Config `primary.model` participates because config is in the layer stack

## Caller Impact

### `plan.py` (resolve_primary_launch_plan)

Before: 
- Creates `pre_resolved` without config, calls `resolve_policies()`, then creates full `resolved` separately
- Two resolution passes with different semantics

After:
- Loads profile using resolved agent
- Single `resolve()` call with all four layers
- Passes resolved + profile to `resolve_policies()` (or inlines the logic)
- `resolve_policies()` becomes simpler — just derivation + adapter lookup + skills

### `prepare.py` (spawn prepare)

Same layer-aware pattern as plan.py, but **different config layer construction**.

Primary path uses `config.primary.*` (per-session overrides):
```python
config_overrides = RuntimeOverrides.from_config(config)  # reads config.primary.*
```

Spawn path uses `config.default_*` (spawn-level defaults):
```python
config_overrides = RuntimeOverrides.from_spawn_config(config)  # reads config.default_*
```

This distinction already exists implicitly — `prepare.py` passes `config.default_agent`
and `config.default_harness` as separate arguments. The refactor makes it explicit by
having two `from_config` variants (or a `context` parameter). The layer stack mechanics
are identical; only what the config layer contains differs.

Add `RuntimeOverrides.from_spawn_config(config)` that reads:
- `config.default_model` (not `config.primary.model`)
- `config.default_harness` (not `config.primary.harness`)
- `config.default_agent` (not `config.primary.agent`)
- Other fields from `config.primary.*` where they exist (effort, sandbox, etc.)

## Edge Cases

### Model alias resolution timing
Model aliases are resolved at two points:
1. **Inside `derive_harness()`** — when a layer's model is used for harness routing, `route_model()` resolves the alias to determine the correct harness. This happens per-layer as each model is encountered.
2. **Inside `resolve_final_model()`** — the final model string is alias-resolved via `resolve_model()` catalog lookup before being returned.

This means alias resolution is encapsulated in the derivation functions, not exposed as a separate step in the caller. Config validators in settings.py also normalize model aliases at load time, so `config.primary.model` is typically already canonical.

### Profile with harness but no model
A profile specifying `harness: codex` but no model should use the codex harness and let the codex adapter pick its default model. The new design handles this: `resolved.harness = "codex"`, `resolved.model = None`, derivation keeps codex, final model comes from `config.default_model_for_harness("codex")`.

### Config model + no harness anywhere
`config.primary.model = "sonnet"`, no harness specified anywhere. New design: `resolved.model = "sonnet"`, `resolved.harness = None`, derivation derives harness from sonnet → claude. Correct.
