# Phase 1: Field Inventory & Consistency Drift Test

## Scope

Create a machine-readable inventory of every configurable field across all five configuration layers (ENV, CLI, Config TOML, YAML profile, spawn CLI). Write a pytest test that compares these field sets and fails when a field exists in one layer but is missing from another — unless it appears in an explicit exclusion set. The exclusion set IS the audit: it documents every known gap.

## Why

This is the foundation for all other phases. It catches drift at CI time, documents current gaps machine-readably, and provides a regression guard as subsequent phases close gaps.

## Files to Create

- `tests/test_config_layer_consistency.py` — the drift test

## Files to Read (not modify)

- `src/meridian/lib/config/settings.py` — ENV var specs in `_env_alias_overrides()` (lines 450-512), `PrimaryConfig` model (lines 548-587), TOML key handling in `_normalize_primary_table()` (lines 267-317)
- `src/meridian/lib/catalog/agent.py` — `AgentProfile` model (lines 31-49)
- `src/meridian/lib/ops/spawn/models.py` — `SpawnCreateInput` model (lines 20-47)
- `src/meridian/cli/spawn.py` — spawn CLI flags in `_spawn_create()` (lines 63-217)
- `src/meridian/cli/main.py` — primary CLI flags in `root()` (lines 261-329) and `_run_primary_launch()` (lines 460-552)
- `src/meridian/lib/launch/types.py` — `LaunchRequest` model (lines 12-28)

## Approach

### 1. Define canonical field sets

Build Python sets for each layer by inspecting actual code artifacts:

```python
# Universal fields: should exist across applicable layers
UNIVERSAL_FIELDS = {
    "model", "harness", "agent", "sandbox", "thinking",
    "approval", "autocompact", "timeout", "budget", "max_turns", "skills",
}

# Extract from each layer:
ENV_FIELDS = set of field names parsed from _env_alias_overrides env_specs
CONFIG_FIELDS = set of field names from PrimaryConfig + top-level MeridianConfig
PROFILE_FIELDS = set of field names from AgentProfile (behavioral fields only)
SPAWN_CLI_FIELDS = set of field names from SpawnCreateInput (behavioral fields only)
PRIMARY_CLI_FIELDS = set of field names from LaunchRequest + root() flags
```

### 2. Build the exclusion set

The exclusion set documents fields that are legitimately restricted to specific layers:

```python
# Fields that should NOT be in certain layers (with reason)
LEGITIMATE_RESTRICTIONS = {
    ("tools", "ENV"): "Complex structured data",
    ("tools", "CLI"): "Complex structured data",
    ("tools", "Config"): "Complex structured data",
    ("mcp_tools", "ENV"): "Complex structured data",
    ("mcp_tools", "CLI"): "Complex structured data",
    ("mcp_tools", "Config"): "Complex structured data",
    ("skills", "ENV"): "Not global default",
    ("skills", "Config"): "Not global default",
    ("max_depth", "Profile"): "Global safety limit",
    ("max_depth", "CLI"): "Global safety limit",
    # ... etc per design spec table
}

# Known gaps (Phase 3 will close these)
KNOWN_GAPS = {
    ("sandbox", "ENV"): "Phase 3.1",
    ("sandbox", "Config"): "Phase 3.1",
    ("sandbox", "PrimaryCLI"): "Phase 3.2",
    ("thinking", "ENV"): "Phase 3.1",
    ("thinking", "Config"): "Phase 3.1",
    ("thinking", "PrimaryCLI"): "Phase 3.2",
    ("approval", "ENV"): "Phase 3.1",
    ("approval", "Config"): "Phase 3.1",
    ("approval", "PrimaryCLI"): "Phase 3.2",
    ("timeout", "ENV"): "Phase 3.1",
    ("timeout", "Config"): "Phase 3.1",
    ("timeout", "PrimaryCLI"): "Phase 3.2",
    ("budget", "PrimaryCLI"): "Phase 3.2",
    ("max_turns", "PrimaryCLI"): "Phase 3.2",
    ("skills", "PrimaryCLI"): "Phase 3.2",
}
```

### 3. The test

```python
def test_universal_field_coverage():
    """Every universal field must exist in all applicable layers,
    unless explicitly excluded."""
    for field in UNIVERSAL_FIELDS:
        for layer in ["ENV", "Config", "Profile", "SpawnCLI", "PrimaryCLI"]:
            if (field, layer) in LEGITIMATE_RESTRICTIONS:
                continue
            if (field, layer) in KNOWN_GAPS:
                continue
            assert field in LAYER_FIELD_SETS[layer], (
                f"Field '{field}' missing from {layer} layer. "
                f"Add it or document the exclusion."
            )

def test_no_undocumented_fields():
    """Every field in any layer must be in UNIVERSAL_FIELDS or
    documented as layer-specific."""
    ...
```

### 4. Inventory output

The test file itself IS the machine-readable inventory. The `KNOWN_GAPS` dict is the audit artifact that subsequent phases consume. When a phase closes a gap, it removes entries from `KNOWN_GAPS` — if it forgets, the test fails because the field now exists but is still listed as a gap.

## Patterns to Follow

- See existing test files in `tests/` for test structure and imports
- Use `frozenset` for immutable field sets
- Keep the test self-contained — don't import runtime code, just define the expected field sets statically

## Constraints

- Do NOT import and introspect runtime models (fragile, breaks on refactors). Define field sets declaratively.
- The test must pass against the CURRENT codebase (before any other phases run)
- Use `pytest` conventions (function-based tests, descriptive names)

## Verification Criteria

- [ ] `uv run pytest tests/test_config_layer_consistency.py -v` passes
- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes
- [ ] `KNOWN_GAPS` dict contains exactly the gaps listed in the design spec
- [ ] Adding a field to one layer without updating others would cause test failure
