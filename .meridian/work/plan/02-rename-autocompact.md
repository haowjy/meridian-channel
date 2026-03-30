# Phase 2: Rename autocompact_pct → autocompact

## Scope

Rename the config TOML field `primary.autocompact_pct` to `primary.autocompact` for naming consistency with the YAML profile and CLI layers. Keep the old name as a deprecated alias so existing config files don't break.

## Why

The design spec identifies `autocompact_pct` vs `autocompact` as a naming inconsistency. Every other layer already uses `autocompact`. The config layer should match.

## Files to Modify

### `src/meridian/lib/config/settings.py`

1. **`PrimaryConfig` model (line 553)**: Rename field `autocompact_pct` → `autocompact`. The type stays `int | None`. Update the validator `_validate_autocompact_pct` → `_validate_autocompact`. Update the error messages from `'primary.autocompact_pct'` to `'primary.autocompact'`.

2. **`_normalize_primary_table()` (lines 267-317)**: Accept both `"autocompact"` (new) and `"autocompact_pct"` (deprecated alias) as TOML keys. When the deprecated name is used, emit `logger.warning("Config key 'primary.autocompact_pct' is deprecated; use 'primary.autocompact'.")`. Both map to the `"autocompact"` key in the output dict.

3. **Constants**: Rename `_PRIMARY_AUTOCOMPACT_PCT_MIN` → `_PRIMARY_AUTOCOMPACT_MIN` and `_PRIMARY_AUTOCOMPACT_PCT_MAX` → `_PRIMARY_AUTOCOMPACT_MAX` (or keep as-is since they're private — judgment call, but rename is cleaner).

### `src/meridian/lib/launch/plan.py`

4. **`resolve_primary_launch_plan()` (line 145)**: Currently references `resolved_config.primary.harness`. Confirm it does NOT reference `autocompact_pct` directly — if it does, update to `autocompact`. (Current code doesn't reference autocompact in launch/plan.py, so this may be no-op.)

### Consumers to check (read-only verification)

5. **`src/meridian/lib/ops/spawn/prepare.py`**: The `build_create_payload` function (line 363) reads `profile.autocompact` — this is the profile field, not the config field. Confirm no reference to `config.primary.autocompact_pct`.

6. **`src/meridian/cli/main.py`**: The `root()` and `_run_primary_launch()` functions don't reference `autocompact_pct`. The `--autocompact` CLI flag already uses the right name.

## Interface Contract

```python
class PrimaryConfig(BaseModel):
    autocompact: int | None = None  # was autocompact_pct
    # ... other fields unchanged
```

TOML parsing accepts both:
```toml
[primary]
autocompact = 80       # new canonical name
autocompact_pct = 80   # deprecated alias, emits warning
```

ENV var `MERIDIAN_AUTOCOMPACT` is NOT added in this phase (Phase 3.1 handles ENV expansion). The existing config access path `config.primary.autocompact_pct` becomes `config.primary.autocompact`.

## Constraints

- The old TOML key `autocompact_pct` MUST still work (deprecated alias)
- The deprecation warning must log, not error
- If both `autocompact` and `autocompact_pct` appear in the same TOML file, the new name wins with a warning about the duplicate
- Do NOT add ENV var support — that's Phase 3.1

## Verification Criteria

- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes
- [ ] `uv run pytest-llm` passes
- [ ] A TOML config with `primary.autocompact_pct = 80` still loads without error
- [ ] A TOML config with `primary.autocompact = 80` loads correctly
- [ ] `config.primary.autocompact` returns the configured value (not `config.primary.autocompact_pct`)
