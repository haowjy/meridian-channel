# Step 3: Wire Resolution Through Spawn + Primary Paths

## Scope

Replace scattered per-field precedence logic in `prepare.py`, `plan.py`, and `resolve.py` with calls to `RuntimeOverrides.resolve()`. After this step, both spawn and primary launch use the same resolution function for all tuning-knob fields.

This is the highest-risk step — it touches the two main launch codepaths and the shared policy resolution. Use a stronger reasoning model.

## Files to Modify

- `src/meridian/lib/launch/resolve.py` — update `resolve_policies` interface
- `src/meridian/lib/ops/spawn/prepare.py` — wire resolve() into spawn path
- `src/meridian/lib/launch/plan.py` — wire resolve() into primary path

## Dependencies

- **Requires**: Step 1 (RuntimeOverrides model, classmethods, resolve function) and Step 2 (config loading no longer injects RuntimeOverrides ENV vars into config).
- **Independent of**: Nothing — this is the critical integration step.
- **Produces**: Unified resolution that Steps 4a, 4b, and 5 build on.

## What to Change

### 1. Update `resolve_policies()` in resolve.py

**Current**: `resolve_policies()` accepts individual `requested_model`, `requested_harness`, and does its own precedence chain:
```python
# Model precedence: requested > profile > harness_default > config.default_model
resolved_model = requested_model.strip()
if not resolved_model and profile is not None and profile.model:
    resolved_model = profile.model.strip()
# ... more fallback logic
```

**New**: Accept a pre-resolved `RuntimeOverrides` for model and harness values. The caller builds layers and calls `resolve()` before calling `resolve_policies()`.

Change the signature — replace `requested_model: str` and `requested_harness: str | None` with `overrides: RuntimeOverrides`:

```python
from meridian.lib.core.overrides import RuntimeOverrides

def resolve_policies(
    *,
    repo_root: Path,
    overrides: RuntimeOverrides,          # <-- replaces requested_model + requested_harness
    requested_agent: str | None,
    config: MeridianConfig,
    harness_registry: HarnessRegistry,
    configured_default_agent: str | None = None,
    builtin_default_agent: str = "",
    configured_default_harness: str = "claude",
    skills_readonly: bool = True,
) -> ResolvedPolicies:
```

Inside, use `overrides.model` and `overrides.harness` instead of `requested_model` and `requested_harness`. **Keep the existing model routing logic** (resolve_harness, adapter lookup, harness-default-model fallback) — RuntimeOverrides provides the winning values, resolve_policies does semantic routing.

Specifically, the model fallback chain becomes:
```python
resolved_model = (overrides.model or "").strip()
# Profile model and config model are already resolved via RuntimeOverrides.resolve()
# before this function is called, so we don't repeat that precedence here.

# But keep harness-default model as a separate fallback (it's a harness concern,
# not a layer concern):
if not resolved_model:
    harness_default = config.default_model_for_harness(str(harness_id))
    if harness_default:
        resolved_model = harness_default
if not resolved_model and config.default_model:
    resolved_model = config.default_model
```

Note: `config.default_model_for_harness()` and `config.default_model` are NOT RuntimeOverrides fields — they're routing defaults. Keep this fallback.

The harness resolution similarly uses `overrides.harness` as the explicit override:
```python
explicit_harness = (overrides.harness or "").strip()
profile_harness = ""
if profile is not None and profile.harness:
    profile_harness = profile.harness.strip()
```

Wait — profile harness is already in RuntimeOverrides (from the profile layer). So `overrides.harness` already incorporates the profile's harness through the resolve() call. The only things NOT in overrides are: configured_default_harness and model-routed harness. Keep those as fallbacks.

**Key principle**: `resolve()` handles the 6-layer precedence. `resolve_policies` handles semantic routing that isn't a simple precedence (model→harness routing, adapter lookup, validation).

### 2. Update `build_create_payload()` in prepare.py

**Current**: Manual per-field resolution scattered through the function:
```python
resolved_sandbox = payload.sandbox or (profile.sandbox if profile is not None else None)
resolved_thinking = payload.thinking or (profile.thinking if profile is not None else None)
# etc.
```

**New**: Build layers, call resolve, use resolved values.

After `resolve_policies()` returns (which gives us the profile), build layers:

```python
from meridian.lib.core.overrides import RuntimeOverrides, resolve

cli_overrides = RuntimeOverrides.from_spawn_input(payload)
env_overrides = RuntimeOverrides.from_env()
profile_overrides = RuntimeOverrides.from_agent_profile(profile)
config_overrides = RuntimeOverrides.from_config(runtime_view.config)
resolved = resolve(cli_overrides, env_overrides, profile_overrides, config_overrides)
```

Then replace all manual resolution with resolved values:
- `resolved_sandbox` → `resolved.sandbox`
- `resolved_thinking` → `resolved.thinking`
- `resolved.approval or "default"` for approval
- `resolved.autocompact` for autocompact

**But there's a chicken-and-egg**: `resolve_policies` is called first (to get the profile and adapter), and it needs model/harness from overrides. So the flow becomes:

```python
# 1. Build CLI + ENV + config layers (no profile yet)
cli_overrides = RuntimeOverrides.from_spawn_input(payload)
env_overrides = RuntimeOverrides.from_env()
config_overrides = RuntimeOverrides.from_config(runtime_view.config)

# 2. Pre-resolve without profile (for model/harness to feed resolve_policies)
pre_resolved = resolve(cli_overrides, env_overrides, config_overrides)

# 3. Call resolve_policies with pre-resolved model/harness
policies = resolve_policies(
    repo_root=runtime_view.repo_root,
    overrides=pre_resolved,
    requested_agent=payload.agent,
    config=runtime_view.config,
    # ...
)
profile = policies.profile

# 4. Full resolve with profile layer
profile_overrides = RuntimeOverrides.from_agent_profile(profile)
resolved = resolve(cli_overrides, env_overrides, profile_overrides, config_overrides)

# 5. Use resolved values everywhere
```

This two-pass pattern is necessary because profile resolution depends on model/harness (which agent to load may depend on routing), while the full override resolution includes profile fields.

**Alternatively**, if resolve_policies loads the profile independently of model/harness overrides (which it does — profile is loaded from `requested_agent` or config default), we can do:

```python
# 1. Load profile via resolve_policies (using payload.model/harness directly for routing)
# 2. Build ALL layers including profile
# 3. resolve() once
# 4. Use resolved model/harness for remaining routing in resolve_policies
```

Looking at the actual code: `resolve_policies` loads the profile from `requested_agent` / `configured_default_agent` — that's independent of model/harness. Then it does model/harness precedence. So we can restructure:

```python
# resolve_policies can be split into:
# - profile loading (agent resolution)
# - model/harness resolution (now via RuntimeOverrides)
# - adapter lookup + routing
```

But that's a bigger refactor. **Simpler approach**: keep resolve_policies mostly intact. Just replace its model/harness input with overrides. The profile is loaded inside resolve_policies as before. Then the caller does a second resolve() pass with the profile to get the full resolved overrides for thinking/sandbox/etc.

### 3. Update `resolve_primary_launch_plan()` in plan.py

Same pattern as prepare.py:

```python
cli_overrides = RuntimeOverrides.from_launch_request(request)
env_overrides = RuntimeOverrides.from_env()
config_overrides = RuntimeOverrides.from_config(resolved_config)

pre_resolved = resolve(cli_overrides, env_overrides, config_overrides)

policies = resolve_policies(
    repo_root=resolved_root,
    overrides=pre_resolved,
    requested_agent=request.agent,
    config=resolved_config,
    # ...
)
profile = policies.profile

profile_overrides = RuntimeOverrides.from_agent_profile(profile)
resolved = resolve(cli_overrides, env_overrides, profile_overrides, config_overrides)
```

Then replace:
- `profile.thinking if profile is not None else None` → `resolved.thinking`
- `request.approval` → `resolved.approval or "default"`
- `profile.sandbox` → `resolved.sandbox`
- The autocompact handling in plan.py is minimal (it doesn't set autocompact directly), but ensure resolved.autocompact is used wherever autocompact appears.

### Callers of resolve_policies to update

Search for all callers of `resolve_policies()` and update their arguments:
1. `prepare.py::build_create_payload()` — primary caller for spawn path
2. `plan.py::resolve_primary_launch_plan()` — primary caller for primary path

Both need to pass `overrides=pre_resolved` instead of `requested_model=...` and `requested_harness=...`.

## Interface Contract

```python
# From Step 1 — what this step consumes:
class RuntimeOverrides(BaseModel):
    model: str | None = None
    harness: str | None = None
    thinking: str | None = None
    sandbox: str | None = None
    approval: str | None = None
    autocompact: int | None = None
    timeout: float | None = None
    budget: float | None = None
    max_turns: int | None = None

def resolve(*layers: RuntimeOverrides) -> RuntimeOverrides: ...
```

## Constraints

- Do NOT add new fields to SpawnCreateInput, LaunchRequest, or PrimaryConfig. Use existing fields.
- Do NOT add new CLI flags. That's Step 4b.
- Do NOT rename autocompact_pct. That's Step 4a.
- Keep `resolve_policies` as the semantic routing function — don't collapse routing logic into `resolve()`.
- `resolve()` is pure precedence (first-non-none). `resolve_policies` is semantic (model→harness routing, adapter lookup, validation).

## Verification Criteria

- [ ] `uv run pyright` passes with 0 errors
- [ ] `uv run ruff check .` passes
- [ ] `uv run pytest-llm` passes (all existing tests)
- [ ] `uv run meridian spawn --dry-run -m claude-sonnet-4-6 -p "test"` produces the same output as before
- [ ] `uv run meridian --dry-run` produces the same output as before
- [ ] Setting `MERIDIAN_THINKING=high` and running spawn applies thinking=high (ENV layer works)
- [ ] CLI `--thinking high` overrides `MERIDIAN_THINKING=low` (CLI > ENV)
- [ ] Agent profile's thinking value is used when neither CLI nor ENV sets it
