# Phase 3.1: Config Layer Expansion (ENV + Config TOML)

## Scope

Add `sandbox`, `thinking`, `approval`, and `timeout` to the config TOML `[primary]` table and to the ENV var parsing layer. This closes the "Add to ENV" and "Add to Config" columns from the design spec Phase 3 table.

## Why

These four fields exist in YAML profiles and spawn CLI but have no config-layer representation. Users can't set project-wide or user-wide defaults for sandbox mode, thinking budget, approval policy, or timeout — they have to specify them on every invocation.

## Files to Modify

### `src/meridian/lib/config/settings.py`

#### 1. `PrimaryConfig` model (lines 548-587)

Add four new fields:

```python
class PrimaryConfig(BaseModel):
    # ... existing fields ...
    sandbox: str | None = None
    thinking: str | None = None
    approval: str | None = None
    timeout: float | None = None  # minutes, same unit as CLI --timeout
```

Add validators:
- `sandbox`: Validate against the known sandbox values from `agent.py` — `{"read-only", "workspace-write", "full-access", "danger-full-access", "unrestricted"}`. Allow `None` (unset). Use `_normalize_optional_string`.
- `thinking`: Validate against `{"low", "medium", "high", "xhigh"}`. Allow `None`.
- `approval`: Validate against `{"default", "confirm", "auto", "yolo"}`. Allow `None`.
- `timeout`: Validate positive float. Allow `None`.

#### 2. `_normalize_primary_table()` (lines 267-317)

Add parsing for the four new keys in the `for key, value in ...` loop:

```python
if key == "sandbox":
    if not isinstance(value, str):
        raise ValueError(...)
    values[key] = _normalize_optional_string(value, source=f"{source}.sandbox") or None
    continue

if key == "thinking":
    if not isinstance(value, str):
        raise ValueError(...)
    values[key] = _normalize_optional_string(value, source=f"{source}.thinking") or None
    continue

if key == "approval":
    if not isinstance(value, str):
        raise ValueError(...)
    values[key] = _normalize_optional_string(value, source=f"{source}.approval") or None
    continue

if key == "timeout":
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(...)
    values[key] = float(value)
    continue
```

#### 3. `_env_alias_overrides()` (lines 450-512)

Add four new ENV var specs to the `env_specs` tuple:

```python
("MERIDIAN_SANDBOX", ("primary", "sandbox"), "str"),
("MERIDIAN_THINKING", ("primary", "thinking"), "str"),
("MERIDIAN_APPROVAL", ("primary", "approval"), "str"),
("MERIDIAN_TIMEOUT", ("primary", "timeout"), "float"),
```

Place them alongside the other `("primary", ...)` entries for organization.

## Dependencies

- Independent of Phase 1 (audit test) and Phase 2 (rename)
- Phase 3.2 depends on this phase (CLI flags need config fields to read from)

## Interface Contract

After this phase, `MeridianConfig` exposes:

```python
config.primary.sandbox    # str | None — e.g., "workspace-write"
config.primary.thinking   # str | None — e.g., "high"
config.primary.approval   # str | None — e.g., "auto"
config.primary.timeout    # float | None — minutes, e.g., 30.0
```

TOML example:
```toml
[primary]
model = "claude-sonnet-4-6"
sandbox = "workspace-write"
thinking = "high"
approval = "auto"
timeout = 30.0
```

ENV example:
```bash
MERIDIAN_SANDBOX=full-access
MERIDIAN_THINKING=high
MERIDIAN_APPROVAL=yolo
MERIDIAN_TIMEOUT=60
```

## Patterns to Follow

- Match the existing pattern for `budget` in `_normalize_primary_table()` for the `timeout` float field
- Match the existing pattern for `model`/`harness`/`agent` string fields for sandbox/thinking/approval
- Use the same known-value sets as `agent.py` for validation (but don't import from there — define locally or use shared constants)

## Constraints

- Do NOT wire these values to runtime resolution yet (Phase 3.3 handles that)
- Do NOT add CLI flags yet (Phase 3.2 handles that)
- Validation of sandbox/thinking/approval values should warn on unknown values rather than hard-error (match profile parsing behavior in `agent.py`)
- `timeout` is in minutes (consistent with CLI --timeout and config `kill_grace_minutes`)

## Verification Criteria

- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes
- [ ] `uv run pytest-llm` passes
- [ ] A TOML config with `primary.sandbox = "workspace-write"` loads correctly
- [ ] `MERIDIAN_SANDBOX=full-access` is parsed and `config.primary.sandbox == "full-access"`
- [ ] Invalid TOML values for these fields produce clear error messages
