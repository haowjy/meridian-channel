# Step 5: Naming Convention Enforcement Test

## Scope

Write a structural test that introspects `RuntimeOverrides.model_fields` and verifies every field has a matching ENV var, config TOML key, and CLI flag. This replaces hand-maintained consistency checks — if someone adds a field to RuntimeOverrides but forgets a layer, the test catches it.

## Files to Create

- `tests/test_overrides_convention.py` — structural convention test

## Dependencies

- **Requires**: Steps 4a and 4b (all layers complete — test would fail if fields are missing from any layer).
- **Independent of**: Nothing — this is the final validation step.
- **Produces**: Guard against future drift.

## What to Build

### Convention test

The test introspects `RuntimeOverrides.model_fields` and checks three conventions:

#### 1. ENV var convention

Every field `foo_bar` must have a corresponding `MERIDIAN_FOO_BAR` environment variable recognized by `RuntimeOverrides.from_env()`.

Test approach:
```python
def test_every_field_has_env_var():
    """Every RuntimeOverrides field is readable from MERIDIAN_<UPPER_SNAKE> env."""
    import os
    from meridian.lib.core.overrides import RuntimeOverrides

    for field_name in RuntimeOverrides.model_fields:
        env_name = f"MERIDIAN_{field_name.upper()}"
        # Set a test value and verify from_env() picks it up
        test_value = _test_value_for_field(field_name)
        with _env_override(env_name, test_value):
            result = RuntimeOverrides.from_env()
            assert getattr(result, field_name) is not None, (
                f"RuntimeOverrides.from_env() did not read {env_name} for field '{field_name}'"
            )
```

Helper `_test_value_for_field` returns a valid string representation for each field type (e.g., "42" for int fields, "high" for thinking).

Helper `_env_override` is a context manager that sets/unsets an env var.

#### 2. Config TOML convention

Every field must be parseable from `[primary]` TOML section.

Test approach:
```python
def test_every_field_has_config_key():
    """Every RuntimeOverrides field is extractable from PrimaryConfig."""
    from meridian.lib.config.settings import PrimaryConfig
    from meridian.lib.core.overrides import RuntimeOverrides

    # Fields that are intentionally not in PrimaryConfig
    # (budget and max_turns may be here; if they are, great; if not, document why)
    config_fields = set(PrimaryConfig.model_fields.keys())

    for field_name in RuntimeOverrides.model_fields:
        # Check field exists in PrimaryConfig (possibly with alias)
        assert field_name in config_fields or _has_alias(field_name, config_fields), (
            f"RuntimeOverrides field '{field_name}' has no matching PrimaryConfig field. "
            f"Add it to PrimaryConfig or document the exclusion."
        )
```

#### 3. CLI flag convention (spawn)

Every field that has a CLI consumer must have a `--<field>` flag on the spawn command.

Test approach:
```python
def test_every_field_has_spawn_cli_flag():
    """Every RuntimeOverrides field is settable via SpawnCreateInput."""
    from meridian.lib.ops.spawn.models import SpawnCreateInput
    from meridian.lib.core.overrides import RuntimeOverrides

    input_fields = set(SpawnCreateInput.model_fields.keys())
    # Fields not expected on SpawnCreateInput (no consumer in spawn path)
    SPAWN_EXCLUDED = {"budget", "max_turns"}

    for field_name in RuntimeOverrides.model_fields:
        if field_name in SPAWN_EXCLUDED:
            continue
        assert field_name in input_fields, (
            f"RuntimeOverrides field '{field_name}' has no matching SpawnCreateInput field. "
            f"Add it or document the exclusion in SPAWN_EXCLUDED."
        )
```

#### 4. CLI flag convention (primary)

```python
def test_every_field_has_primary_cli_flag():
    """Every RuntimeOverrides field with a consumer has a LaunchRequest field."""
    from meridian.lib.launch.types import LaunchRequest
    from meridian.lib.core.overrides import RuntimeOverrides

    request_fields = set(LaunchRequest.model_fields.keys())
    # Fields not expected on LaunchRequest (no consumer in primary pipeline)
    PRIMARY_EXCLUDED = {"budget", "max_turns"}

    for field_name in RuntimeOverrides.model_fields:
        if field_name in PRIMARY_EXCLUDED:
            continue
        assert field_name in request_fields, (
            f"RuntimeOverrides field '{field_name}' has no matching LaunchRequest field. "
            f"Add it or document the exclusion in PRIMARY_EXCLUDED."
        )
```

### Exclusion lists

The `SPAWN_EXCLUDED` and `PRIMARY_EXCLUDED` sets document intentional gaps. The key property: adding a field to RuntimeOverrides without adding it to CLI models requires explicitly adding it to an exclusion list. This makes "forgot to add the flag" impossible to miss.

When `budget` and `max_turns` get real consumers, remove them from the exclusion sets and the test will enforce their presence.

### from_env round-trip test

```python
def test_from_env_round_trip():
    """from_env reads all fields, resolve produces expected output."""
    import os
    from meridian.lib.core.overrides import RuntimeOverrides, resolve

    env_values = {
        "MERIDIAN_MODEL": "test-model",
        "MERIDIAN_HARNESS": "claude",
        "MERIDIAN_THINKING": "high",
        "MERIDIAN_SANDBOX": "full-access",
        "MERIDIAN_APPROVAL": "auto",
        "MERIDIAN_AUTOCOMPACT": "50",
        "MERIDIAN_TIMEOUT": "30.0",
        "MERIDIAN_BUDGET": "5.0",
        "MERIDIAN_MAX_TURNS": "10",
    }
    # Set all env vars, call from_env, verify all fields populated
    with _env_overrides(env_values):
        result = RuntimeOverrides.from_env()
        for field_name in RuntimeOverrides.model_fields:
            assert getattr(result, field_name) is not None, (
                f"from_env() did not populate '{field_name}'"
            )
```

## Patterns to Follow

- `tests/exec/test_permissions.py` for test structure
- Keep tests focused and self-contained
- Use `monkeypatch` or context managers for env var manipulation

## Constraints

- Tests must introspect `RuntimeOverrides.model_fields` — no hand-maintained field lists in the test itself (except exclusion sets).
- Exclusion sets must have inline documentation explaining WHY each field is excluded.
- Tests should be fast (no I/O, no subprocess calls).

## Verification Criteria

- [ ] `uv run pyright` passes with 0 errors
- [ ] `uv run ruff check .` passes
- [ ] `uv run pytest-llm` passes (including the new test)
- [ ] All convention tests pass
- [ ] Removing a field from SpawnCreateInput causes the test to fail (verify manually)
- [ ] Adding a new field to RuntimeOverrides without updating layers causes the test to fail
