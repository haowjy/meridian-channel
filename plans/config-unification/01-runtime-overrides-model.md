# Step 1: RuntimeOverrides Model

## Scope

Create the shared `RuntimeOverrides` Pydantic model that defines all universal "tuning knob" fields once. Every config layer will use this model. This is the foundation — all later steps depend on it.

## Files to Create

- `src/meridian/lib/core/overrides.py` — the RuntimeOverrides model, classmethods, and resolve function

## Dependencies

- **Requires**: Nothing — this is the foundation step.
- **Independent of**: Step 2 (config loading refactor).
- **Produces**: `RuntimeOverrides` model, `resolve()` function, and `from_*` classmethods that Steps 3-5 consume.

## What to Build

### RuntimeOverrides model

```python
from pydantic import BaseModel, ConfigDict

class RuntimeOverrides(BaseModel):
    """Fields that can be set at any config layer.

    Adding a new tuning knob = add it here. All layers (CLI, ENV, profile,
    config) derive from this model, so drift is structurally impossible.
    """
    model_config = ConfigDict(frozen=True)

    model: str | None = None
    harness: str | None = None
    thinking: str | None = None
    sandbox: str | None = None
    approval: str | None = None
    autocompact: int | None = None
    timeout: float | None = None
    budget: float | None = None
    max_turns: int | None = None
```

All fields are `| None` with `None` default — "not specified at this layer."

### `from_env()` classmethod

Read `MERIDIAN_*` environment variables into a RuntimeOverrides instance. This replaces the RuntimeOverrides-scoped entries currently in `settings.py::_env_alias_overrides()`.

ENV var mapping (use `MERIDIAN_` prefix + UPPER_SNAKE of field name):
- `MERIDIAN_MODEL` → `model` (str)
- `MERIDIAN_HARNESS` → `harness` (str)
- `MERIDIAN_THINKING` → `thinking` (str)
- `MERIDIAN_SANDBOX` → `sandbox` (str)
- `MERIDIAN_APPROVAL` → `approval` (str)
- `MERIDIAN_AUTOCOMPACT` → `autocompact` (int)
- `MERIDIAN_TIMEOUT` → `timeout` (float, in minutes)
- `MERIDIAN_BUDGET` → `budget` (float)
- `MERIDIAN_MAX_TURNS` → `max_turns` (int)

For type coercion, follow the existing pattern from `settings.py`:
- `_parse_env_int` for ints, `_parse_env_float` for floats, strip+validate for strings
- Import or duplicate the small parsing helpers. Prefer importing from settings if they're already public, otherwise duplicate (they're trivial).
- Unset or empty env vars → `None` (not set at this layer).

### `from_agent_profile()` classmethod

Extract RuntimeOverrides fields from an `AgentProfile` instance.

```python
@classmethod
def from_agent_profile(cls, profile: AgentProfile | None) -> "RuntimeOverrides":
    if profile is None:
        return cls()
    return cls(
        model=profile.model,
        harness=profile.harness,
        thinking=profile.thinking,
        sandbox=profile.sandbox,
        approval=profile.approval,
        autocompact=profile.autocompact,
        # AgentProfile has no timeout, budget, max_turns → remain None
    )
```

Import `AgentProfile` from `meridian.lib.catalog.agent`. Use `TYPE_CHECKING` guard to avoid circular imports if needed.

### `from_config()` classmethod

Extract RuntimeOverrides from a loaded `MeridianConfig`. The config's `primary` sub-model has the relevant fields.

```python
@classmethod
def from_config(cls, config: MeridianConfig) -> "RuntimeOverrides":
    return cls(
        model=config.primary.model,
        harness=config.primary.harness,
        autocompact=config.primary.autocompact_pct,  # current name, renamed in Step 4a
        budget=config.primary.budget,
        max_turns=config.primary.max_turns,
        # thinking, sandbox, approval, timeout not in PrimaryConfig yet → remain None
        # Step 4a adds them
    )
```

Import `MeridianConfig` from `meridian.lib.config.settings`. Use `TYPE_CHECKING` guard if needed.

### `from_spawn_input()` classmethod

Extract from `SpawnCreateInput` (CLI flags for spawn command).

```python
@classmethod
def from_spawn_input(cls, payload: SpawnCreateInput) -> "RuntimeOverrides":
    return cls(
        model=payload.model or None,
        harness=payload.harness,
        thinking=payload.thinking,
        sandbox=payload.sandbox,
        approval=payload.approval,
        autocompact=payload.autocompact,
        timeout=payload.timeout,
        # budget, max_turns not on SpawnCreateInput → remain None
    )
```

### `from_launch_request()` classmethod

Extract from `LaunchRequest` (CLI flags for primary command).

```python
@classmethod
def from_launch_request(cls, request: LaunchRequest) -> "RuntimeOverrides":
    return cls(
        model=request.model or None,
        harness=request.harness,
        approval=request.approval if request.approval != "default" else None,
        autocompact=request.autocompact,
        # thinking, sandbox, timeout, budget, max_turns not on LaunchRequest yet
        # Step 4b adds them
    )
```

### `resolve()` function

```python
def resolve(*layers: RuntimeOverrides) -> RuntimeOverrides:
    """Merge config layers by first-non-none precedence.

    Layers are ordered highest-to-lowest priority.
    Typical call: resolve(cli, env, profile, config)
    """
    resolved: dict[str, object] = {}
    for field_name in RuntimeOverrides.model_fields:
        for layer in layers:
            value = getattr(layer, field_name)
            if value is not None:
                resolved[field_name] = value
                break
    return RuntimeOverrides(**resolved)
```

Use variadic `*layers` instead of named parameters — simpler and more flexible than the 5-parameter signature in the design spec. The ordering convention (CLI first, then ENV, etc.) is documented and enforced by callers.

### Validation

Add field validators for known-value fields, consistent with existing validation in `agent.py` and `permissions.py`:

- `thinking`: must be in `{"low", "medium", "high", "xhigh"}` if set
- `sandbox`: must be in `{"read-only", "workspace-write", "full-access", "danger-full-access", "unrestricted"}` if set
- `approval`: must be in `{"default", "confirm", "auto", "yolo"}` if set
- `autocompact`: must be 1-100 if set
- `timeout`: must be > 0 if set
- `budget`: must be > 0 if set
- `max_turns`: must be > 0 if set

Use `@field_validator` for each. Reference the frozensets already defined in `agent.py` and `permissions.py` — import them or define canonical versions here and have those files import from here instead (prefer the latter to centralize).

### `__all__` export

```python
__all__ = ["RuntimeOverrides", "resolve"]
```

## Patterns to Follow

- `src/meridian/lib/core/types.py` for Pydantic model style in the core module
- `src/meridian/lib/config/settings.py` for env parsing helpers (`_parse_env_int`, etc.)
- `src/meridian/lib/catalog/agent.py` for known-value validation frozensets

## Constraints

- Do NOT touch any existing files in this step. This is purely additive.
- Do NOT add CLI flags, TOML keys, or change config loading. That's Steps 2-4.
- Validation values (known thinking levels, sandbox modes, etc.) should be canonical constants defined here, not duplicated from agent.py. Later steps will update agent.py to import from here.

## Verification Criteria

- [ ] `uv run pyright` passes with 0 errors
- [ ] `uv run ruff check .` passes
- [ ] `RuntimeOverrides()` creates an all-None instance
- [ ] `RuntimeOverrides.from_env()` reads the 9 MERIDIAN_* vars and ignores unset ones
- [ ] `resolve(RuntimeOverrides(model="a"), RuntimeOverrides(model="b"))` returns model="a"
- [ ] `resolve(RuntimeOverrides(), RuntimeOverrides(model="b"))` returns model="b"
- [ ] Validators reject invalid values (e.g., thinking="invalid", autocompact=200)
- [ ] `uv run pytest-llm` passes (existing tests unbroken)
