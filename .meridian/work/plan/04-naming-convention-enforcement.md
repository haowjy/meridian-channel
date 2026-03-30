# Phase 4: Naming Convention Enforcement

## Scope

Add a test that validates naming conventions are consistent across all layers, and update the Phase 1 consistency test to remove closed-gap exclusions. Document the naming convention in the test file.

## Why

The design spec Phase 4 defines a naming convention:
- Field name is the canonical identifier: `autocompact` (not `autocompact_pct`)
- ENV var: `MERIDIAN_` + UPPER_SNAKE of field name
- Config TOML: `primary.<field>` for per-session fields, top-level for globals
- CLI flag: `--<field>` (hyphenated)
- YAML key: `<field>` (as-is)

After Phases 2 and 3, all fields should follow this convention. This phase adds the test to enforce it going forward.

## Files to Modify

### `tests/test_config_layer_consistency.py`

1. **Remove closed-gap exclusions**: After Phase 3 closes all gaps, remove entries from `KNOWN_GAPS` for sandbox, thinking, approval, timeout, budget (PrimaryCLI), max_turns (PrimaryCLI), skills (PrimaryCLI). The test should now pass without these exclusions.

2. **Add naming convention test**: New test function that validates:

```python
def test_naming_convention_env_vars():
    """ENV vars follow MERIDIAN_ + UPPER_SNAKE pattern."""
    for field_name, env_name in ENV_FIELD_MAP.items():
        expected = f"MERIDIAN_{field_name.upper()}"
        assert env_name == expected or env_name in KNOWN_ENV_EXCEPTIONS, (
            f"ENV var for '{field_name}' is '{env_name}', expected '{expected}'"
        )

# Known exceptions where ENV name doesn't match simple UPPER_SNAKE:
KNOWN_ENV_EXCEPTIONS = {
    # Global defaults use different scoping prefixes
    "MERIDIAN_DEFAULT_MODEL",    # not MERIDIAN_MODEL (that's primary.model)
    "MERIDIAN_DEFAULT_HARNESS",  # not MERIDIAN_HARNESS (that's primary.harness)
    "MERIDIAN_DEFAULT_AGENT",    # not MERIDIAN_AGENT (that's primary.agent)
    "MERIDIAN_PRIMARY_AGENT",    # orchestrator role, different from default_agent
    # Per-harness model routing
    "MERIDIAN_HARNESS_MODEL_CLAUDE",
    "MERIDIAN_HARNESS_MODEL_CODEX",
    "MERIDIAN_HARNESS_MODEL_OPENCODE",
}

def test_naming_convention_config_keys():
    """Config TOML keys match canonical field names."""
    for field_name in PER_SESSION_FIELDS:
        assert field_name in CONFIG_PRIMARY_FIELDS, (
            f"Per-session field '{field_name}' missing from [primary] config table"
        )

def test_naming_convention_cli_flags():
    """CLI flags use --<field> (hyphenated) pattern."""
    for field_name in UNIVERSAL_FIELDS:
        if (field_name, "PrimaryCLI") in LEGITIMATE_RESTRICTIONS:
            continue
        expected_flag = f"--{field_name.replace('_', '-')}"
        assert expected_flag in PRIMARY_CLI_FLAGS, (
            f"Primary CLI missing flag '{expected_flag}' for field '{field_name}'"
        )
```

3. **Document the convention**: Add a module docstring explaining the naming rules.

## Dependencies

- Requires all of Phase 1, 2, 3.1, 3.2, 3.3 to be complete
- Run last to validate the full picture

## Constraints

- Exception lists must have comments explaining WHY the exception exists
- The autocompact_pct deprecated alias should NOT appear as a naming violation (it's a backward-compat alias, the canonical name is `autocompact`)
- Don't break existing test structure from Phase 1

## Verification Criteria

- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes
- [ ] `uv run pytest tests/test_config_layer_consistency.py -v` passes with zero exclusions for Phase 3 gaps
- [ ] Adding a new field with inconsistent naming would cause test failure
- [ ] The `KNOWN_GAPS` dict is empty (all gaps closed)
