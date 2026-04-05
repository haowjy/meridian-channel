# Resolve Precedence Refactor

## Problem

The resolve pipeline in `src/meridian/lib/launch/resolve.py` encodes precedence as implicit code ordering (if/elif chains). This makes it easy to violate the invariant:

**CLI override > ENV > profile > project config > user config > builtin default**

Derived fields must inherit the precedence level of their source (e.g., harness derived from an overridden model should be treated as an override, not a default).

## Known Violations

From investigator audit (p907, p908, p906):

### High severity
1. **`-m` override loses to profile harness** — `resolve_policies()` checks `profile_harness` before model-derived harness. `-m sonnet` on a codex-profiled agent errors instead of deriving claude harness.
2. **Harness resolves before config default model** — harness is locked in at lines 210-222, then `config.default_model` is applied at lines 233-239. Config model never gets to derive its harness.
3. **`config.primary.model` is dead** — `plan.py` passes only CLI+env overrides into `resolve_policies()`, not config overrides. `primary.model` never enters resolution.

### Medium severity
4. **`primary.agent` is dead** — `plan.py` passes `defaults.primary_agent`, never consults `primary.agent`.
5. **`defaults.harness` ignored for primary launch** — hardcodes `"claude"` fallback.
6. **Config-sourced harnesses skip compatibility validation** — only CLI/profile harnesses are validated against the resolved model.

### Low severity
7. **`--approval default` can't override profile approval** — maps to `None`, indistinguishable from "not specified".
8. **`_source_for_key` display bug** — misreports source in some cases.

## Design Goal

Make the precedence invariant **structurally impossible to violate**. The design should ensure:

1. All sources (CLI, env, profile, project config, user config, builtin) produce the same shaped data
2. Resolution is a single generic pass: first non-None across layers wins
3. Derived fields (harness from model) resolve AFTER all primaries are resolved, not during
4. Adding a new source or field cannot accidentally break precedence because the mechanism enforces it

## Constraints

- Must be backwards compatible — existing configs, profiles, and CLI flags all work the same
- The `RuntimeOverrides.resolve()` pattern already exists and works for some fields — extend it, don't replace with something incompatible
- `settings.py` pydantic-settings layer ordering is already correct (init > env > project > user) — don't break it
- Keep it simple — this is a refactor, not a rewrite
