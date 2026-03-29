# Step 2: Config Loading Refactor

## Scope

Fix two problems in `settings.py`: (1) ENV vars for RuntimeOverrides fields are baked into config loading via pydantic-settings — separate them so `RuntimeOverrides.from_env()` handles them instead, and (2) TOML precedence is inverted — project should win over user, not the other way around.

## Files to Modify

- `src/meridian/lib/config/settings.py` — config loading mechanics

## Dependencies

- **Requires**: Nothing from Step 1 (independent — edits different file).
- **Independent of**: Step 1 (RuntimeOverrides model creation).
- **Produces**: Correct config loading where (a) project TOML > user TOML and (b) RuntimeOverrides-scoped ENV vars are no longer injected into MeridianConfig.

## What to Change

### 1. Fix TOML precedence in `settings_customise_sources`

**Current** (line 706-711):
```python
return (
    init_settings,
    cast("PydanticBaseSettingsSource", layered_env_source),
    cast("PydanticBaseSettingsSource", user_toml_source),
    cast("PydanticBaseSettingsSource", project_toml_source),
)
```

pydantic-settings applies sources left-to-right with later sources overriding earlier ones. Current order: init < env < user < project. This means project wins over user — BUT `layered_env_source` wins over everything except project, which means ENV vars are resolved incorrectly for non-RuntimeOverrides fields too.

Actually, looking more carefully: pydantic-settings source order is **first source wins** (highest priority first). So the current order gives: `init > env > user > project`, making user TOML beat project TOML. This is the bug.

**Fix**: Swap user and project so project wins:
```python
return (
    init_settings,
    cast("PydanticBaseSettingsSource", layered_env_source),
    cast("PydanticBaseSettingsSource", project_toml_source),
    cast("PydanticBaseSettingsSource", user_toml_source),
)
```

This gives: `init > env > project > user`. ENV still beats both TOML sources for operational overrides (max_depth, etc.) which is correct — those are non-RuntimeOverrides fields and should be env-overrideable.

### 2. Remove RuntimeOverrides fields from `_env_alias_overrides()`

**Current** `_env_alias_overrides()` reads these RuntimeOverrides-scoped env vars and injects them into config:
- `MERIDIAN_MODEL` → `("primary", "model")`
- `MERIDIAN_HARNESS` → `("primary", "harness")`
- `MERIDIAN_MAX_TURNS` → `("primary", "max_turns")`
- `MERIDIAN_MAX_INPUT_TOKENS` → `("primary", "max_input_tokens")`
- `MERIDIAN_MAX_OUTPUT_TOKENS` → `("primary", "max_output_tokens")`
- `MERIDIAN_BUDGET` → `("primary", "budget")`
- `MERIDIAN_AGENT` → `("primary", "agent")`

**Remove** all entries that map to fields handled by RuntimeOverrides. The RuntimeOverrides fields are: `model`, `harness`, `budget`, `max_turns`. Also `autocompact` once renamed.

**Keep** these non-RuntimeOverrides env vars in `_env_alias_overrides()`:
- `MERIDIAN_MAX_DEPTH` → `max_depth`
- `MERIDIAN_MAX_RETRIES` → `max_retries`
- `MERIDIAN_RETRY_BACKOFF_SECONDS` → `retry_backoff_seconds`
- `MERIDIAN_KILL_GRACE_MINUTES` → `kill_grace_minutes`
- `MERIDIAN_GUARDRAIL_TIMEOUT_MINUTES` → `guardrail_timeout_minutes`
- `MERIDIAN_WAIT_TIMEOUT_MINUTES` → `wait_timeout_minutes`
- `MERIDIAN_PRIMARY_AGENT` → `primary_agent`
- `MERIDIAN_DEFAULT_AGENT` → `default_agent`
- `MERIDIAN_DEFAULT_MODEL` → `default_model`
- `MERIDIAN_DEFAULT_HARNESS` → `default_harness`
- `MERIDIAN_HARNESS_MODEL_CLAUDE` → `harness.claude`
- `MERIDIAN_HARNESS_MODEL_CODEX` → `harness.codex`
- `MERIDIAN_HARNESS_MODEL_OPENCODE` → `harness.opencode`
- `MERIDIAN_FORMAT` → `output.format`

Also keep:
- `MERIDIAN_MAX_INPUT_TOKENS` → stays (layer-specific to config, not RuntimeOverrides)
- `MERIDIAN_MAX_OUTPUT_TOKENS` → stays
- `MERIDIAN_AGENT` → stays (this is `primary.agent` for agent selection, NOT a RuntimeOverrides field)

**Specifically remove from `_env_alias_overrides()`**:
- `("MERIDIAN_MODEL", ("primary", "model"), "str")` — handled by RuntimeOverrides.from_env()
- `("MERIDIAN_HARNESS", ("primary", "harness"), "str")` — handled by RuntimeOverrides.from_env()
- `("MERIDIAN_MAX_TURNS", ("primary", "max_turns"), "int")` — handled by RuntimeOverrides.from_env()
- `("MERIDIAN_BUDGET", ("primary", "budget"), "float")` — handled by RuntimeOverrides.from_env()

**Do NOT remove `MERIDIAN_AGENT`** — agent selection is NOT a RuntimeOverrides field (it's role-based defaults, per design spec "Fields that stay layer-specific").

### 3. Update docstring on `load_config()`

Current docstring says:
```python
"""Load config with precedence: defaults < project < user < environment."""
```

Update to:
```python
"""Load config with precedence: defaults < user < project < environment.

RuntimeOverrides fields (model, harness, thinking, etc.) are NOT loaded
from ENV here — they are read separately via RuntimeOverrides.from_env().
"""
```

## Patterns to Follow

- `src/meridian/lib/config/settings.py` — follow existing style for the source customization pattern

## Constraints

- Do NOT change `PrimaryConfig` schema (no field renames yet — that's Step 4a).
- Do NOT add new TOML keys. Keep existing schema exactly as-is.
- Do NOT import or reference RuntimeOverrides. This step is purely about config loading mechanics.
- Preserve all existing non-RuntimeOverrides ENV var behavior.

## Verification Criteria

- [ ] `uv run pyright` passes with 0 errors
- [ ] `uv run ruff check .` passes
- [ ] `uv run pytest-llm` passes (existing tests unbroken)
- [ ] Config loads correctly from TOML files (smoke test `uv run meridian config show` if available, or inspect via Python)
- [ ] When both user TOML and project TOML set `primary.model`, project TOML wins
- [ ] Non-RuntimeOverrides ENV vars (MERIDIAN_MAX_DEPTH, etc.) still override config
- [ ] MERIDIAN_MODEL env var no longer affects `config.primary.model` (it's handled by RuntimeOverrides separately in Step 3)
