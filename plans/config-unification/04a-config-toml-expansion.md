# Step 4a: Config TOML Schema Expansion + autocompact Rename

## Scope

Add missing RuntimeOverrides fields to config TOML parsing so all 9 fields are configurable via `[primary]` in both project and user TOML. Rename `autocompact_pct` → `autocompact` with backward-compatible alias.

## Files to Modify

- `src/meridian/lib/config/settings.py` — TOML parsing and PrimaryConfig model
- `src/meridian/lib/core/overrides.py` — update `from_config()` for new fields
- `src/meridian/lib/catalog/agent.py` — import canonical known-value sets from overrides.py (optional cleanup)

## Dependencies

- **Requires**: Step 3 (resolution wired — so new config fields flow through resolve()).
- **Independent of**: Step 4b (CLI flags — different files).
- **Produces**: All 9 RuntimeOverrides fields readable from TOML config.

## What to Change

### 1. Expand `PrimaryConfig` model

Add missing fields:
```python
class PrimaryConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    autocompact: int | None = None       # renamed from autocompact_pct
    autocompact_pct: int | None = None   # deprecated alias, mapped to autocompact
    model: str | None = None
    harness: str | None = None
    max_turns: int | None = None
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    budget: float | None = None
    agent: str | None = None
    # NEW fields:
    thinking: str | None = None
    sandbox: str | None = None
    approval: str | None = None
    timeout: float | None = None         # in minutes, consistent with CLI
```

For `autocompact_pct` → `autocompact` rename:
- Accept both `autocompact` and `autocompact_pct` in TOML
- If both are set, `autocompact` wins (it's the canonical name)
- If only `autocompact_pct` is set, use it
- Log a deprecation warning when `autocompact_pct` is used
- Keep the same 1-100 validation range

Add validators for new string fields using the canonical known-value sets from `overrides.py`:
```python
@field_validator("thinking")
@classmethod
def _validate_thinking(cls, value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    from meridian.lib.core.overrides import KNOWN_THINKING_VALUES
    if normalized not in KNOWN_THINKING_VALUES:
        raise ValueError(f"Invalid thinking value: {value!r}")
    return normalized
```

Similarly for `sandbox` and `approval`.

### 2. Update `_normalize_primary_table()` in settings.py

Add parsing for new keys in the primary TOML table:

```python
if key == "thinking":
    if not isinstance(value, str):
        raise ValueError(...)
    values[key] = _normalize_required_string(value, source=f"{source}.thinking")
    continue

if key == "sandbox":
    if not isinstance(value, str):
        raise ValueError(...)
    values[key] = _normalize_required_string(value, source=f"{source}.sandbox")
    continue

if key == "approval":
    if not isinstance(value, str):
        raise ValueError(...)
    values[key] = _normalize_required_string(value, source=f"{source}.approval")
    continue

if key == "timeout":
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(...)
    values[key] = float(value)
    continue

if key == "autocompact":
    # New canonical name (same validation as autocompact_pct)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(...)
    if not (_PRIMARY_AUTOCOMPACT_PCT_MIN <= value <= _PRIMARY_AUTOCOMPACT_PCT_MAX):
        raise ValueError(...)
    values[key] = value
    continue
```

Handle the `autocompact` / `autocompact_pct` coexistence:
- Both accepted
- After parsing, if `autocompact_pct` is present but `autocompact` is not, copy it over
- Log deprecation warning for `autocompact_pct`

### 3. Update `from_config()` in overrides.py

Now that PrimaryConfig has all 9 fields:
```python
@classmethod
def from_config(cls, config: MeridianConfig) -> "RuntimeOverrides":
    primary = config.primary
    return cls(
        model=primary.model,
        harness=primary.harness,
        thinking=primary.thinking,
        sandbox=primary.sandbox,
        approval=primary.approval,
        autocompact=primary.autocompact or primary.autocompact_pct,  # compat
        timeout=primary.timeout,
        budget=primary.budget,
        max_turns=primary.max_turns,
    )
```

### 4. Update autocompact references

Search for `autocompact_pct` throughout the codebase and update to `autocompact`:

- `settings.py`: PrimaryConfig field + validator + TOML parsing (handled above)
- `overrides.py`: `from_config()` (handled above)
- `command.py::build_launch_env()`: `default_autocompact_pct` parameter name and CLAUDE_AUTOCOMPACT_PCT_OVERRIDE env var name (keep the Claude env var name unchanged — that's Claude's own convention)
- `agent.py`: already uses `autocompact` (no change needed)

## Patterns to Follow

- Existing `_normalize_primary_table()` for TOML key parsing style
- Existing `PrimaryConfig` validators for validation patterns

## Constraints

- Keep `autocompact_pct` as a deprecated alias — do NOT break existing TOML configs.
- Do NOT change CLI flags (that's Step 4b).
- Use canonical known-value sets from `overrides.py` — don't re-define them.

## Verification Criteria

- [ ] `uv run pyright` passes with 0 errors
- [ ] `uv run ruff check .` passes
- [ ] `uv run pytest-llm` passes
- [ ] TOML with `[primary]\nthinking = "high"` loads successfully
- [ ] TOML with `[primary]\nsandbox = "full-access"` loads successfully
- [ ] TOML with `[primary]\napproval = "auto"` loads successfully
- [ ] TOML with `[primary]\ntimeout = 30.0` loads successfully
- [ ] TOML with `[primary]\nautocompact = 50` loads (new name)
- [ ] TOML with `[primary]\nautocompact_pct = 50` still loads (deprecated alias)
- [ ] Invalid values are rejected (e.g., `thinking = "invalid"`)
- [ ] `from_config()` returns all 9 fields from a fully-populated config
