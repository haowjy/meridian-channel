# Phase 2: Add `from_spawn_config()` Factory Method

## Scope

Add a `RuntimeOverrides.from_spawn_config(config)` classmethod that reads spawn-level defaults (`config.default_model`, `config.default_harness`, `config.default_agent`) instead of primary-level settings. This makes the primary vs spawn config distinction explicit rather than implicit.

Currently `prepare.py` passes `config.default_agent`, `config.default_harness`, etc. as separate arguments to `resolve_policies()`. After this phase, those values come from a single config layer in the override stack.

## Files to Modify

### `src/meridian/lib/core/overrides.py`

Add new classmethod after `from_config()`:

```python
@classmethod
def from_spawn_config(cls, config: MeridianConfig | None) -> RuntimeOverrides:
    """Build overrides from spawn-level config defaults.
    
    Unlike from_config() which reads config.primary.*, this reads
    config.default_* fields used for spawned subagents.
    """
    if config is None:
        return cls()
    return cls(
        model=_normalize_optional_string(config.default_model) or None,
        harness=_normalize_optional_string(config.default_harness) or None,
        agent=_normalize_optional_string(config.default_agent) or None,
        # Behavioral overrides (effort, sandbox, etc.) come from config.primary.*
        # even for spawns — they're session-wide settings, not spawn-specific.
        effort=config.primary.effort if hasattr(config, 'primary') else None,
        sandbox=config.primary.sandbox if hasattr(config, 'primary') else None,
        approval=config.primary.approval if hasattr(config, 'primary') else None,
        autocompact=config.primary.autocompact if hasattr(config, 'primary') else None,
        timeout=config.primary.timeout if hasattr(config, 'primary') else None,
    )
```

**Important**: Check the `MeridianConfig` model to verify:
- `config.default_model` is `str` (may be empty string, not None) — use `or None` to convert empty to None
- `config.default_harness` is `str` — same treatment
- `config.default_agent` is `str` — same treatment
- Whether `config.primary` has `effort`, `sandbox`, etc. fields — if `PrimaryConfig` doesn't have these, omit them from this factory

## Dependencies

- Requires Phase 1 (for `agent` field on `RuntimeOverrides`)

## Interface Contract

`RuntimeOverrides.from_spawn_config(config)` returns an overrides layer populated from spawn-level config defaults. Empty strings from config are normalized to `None` so they don't participate in first-non-None merge.

## Verification Criteria

- [ ] `uv run pyright` passes (0 errors)
- [ ] `uv run ruff check .` passes
- [ ] `uv run pytest-llm` passes
- [ ] Manual check: `from_spawn_config(config)` with `config.default_model = "gpt-5.3-codex"` returns `RuntimeOverrides(model="gpt-5.3-codex")`
- [ ] Manual check: `from_spawn_config(config)` with `config.default_model = ""` returns `RuntimeOverrides(model=None)` (empty string → None)

## Agent Staffing

- 1 coder (default model)
- 1 reviewer (default model, correctness focus)
- 1 verifier
