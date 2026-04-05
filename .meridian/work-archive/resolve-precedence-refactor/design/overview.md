# Resolve Precedence Refactor: Design Overview

## Problem

The resolve pipeline has two separate resolution mechanisms:

1. **`RuntimeOverrides.resolve()`** — clean layered first-non-None for scalar fields (effort, sandbox, approval, autocompact, timeout). Works correctly.
2. **Ad-hoc if/elif chains in `resolve_policies()`** — handles model, harness, and agent. Violates the precedence invariant in multiple ways (see requirements.md).

The root cause: model/harness resolution was built as procedural logic with implicit ordering, rather than as a declarative layer stack with a generic merge.

## Invariant

```
CLI override > ENV > profile > project config > user config > builtin default
```

Derived fields (harness from model) inherit the precedence of their source.

## Approach: Unified Layer Stack with Two-Phase Resolution

Extend the existing `RuntimeOverrides` pattern to cover ALL resolvable fields uniformly, then add a second derivation pass for dependent fields.

### Phase 1: Resolve Primary Fields

All sources produce the same `RuntimeOverrides` shape. A single `resolve(*layers)` call merges them with first-non-None semantics in strict precedence order. This already works for effort/sandbox/etc. The change is to **actually pass all layers into `resolve_policies()`** and use the resolved result for model selection too.

Currently, `plan.py` does:
```python
pre_resolved = resolve(cli_overrides, env_overrides)  # excludes config!
policies = resolve_policies(..., overrides=pre_resolved, ...)
# Inside resolve_policies: ad-hoc model/harness resolution
```

After refactor:
```python
all_layers = (cli_overrides, env_overrides, profile_overrides, config_overrides)
resolved = resolve(*all_layers)
# resolved.model, resolved.harness now follow correct precedence
```

The challenge: **profile_overrides aren't known until the profile is loaded**, and which profile to load may depend on config. So resolution happens in two steps:

1. **Load profile**: Use agent from CLI > ENV > config > builtin default (simple first-non-None on agent field only)
2. **Resolve all fields**: `resolve(cli, env, profile, config)` for model, harness, effort, etc.

### Phase 2: Derive Dependent Fields (Layer-Aware)

After profile loading and layer construction, derive dependent fields by **scanning layers directly** — not from the pre-merged result. This is the critical design point that all reviewers flagged.

`derive_harness()` scans layers in precedence order:
- At each layer: if it specifies harness, use that harness. If it specifies model (but not harness), derive harness from model. If neither, continue to next layer.
- Fallback: `config.default_harness`.

This ensures a CLI `-m sonnet` derives `claude` harness and wins over a profile's `harness: codex`, because the CLI layer is scanned first. The derived harness inherits the precedence of the model that produced it — structurally, not by convention.

After harness is known, `resolve_final_model()` applies harness-specific model defaults (e.g., `config.harness.codex = "o3"`) for cases where no layer specified a model.

### Why Not Build Something New?

The `RuntimeOverrides` + `resolve()` pattern already works. It's tested, understood, and handles the hard parts (validation, normalization, first-non-None merge). Building a new resolution framework would be more work and more risk for no additional capability.

## Changes by File

### `overrides.py` — Minimal changes
- Add `agent` field to `RuntimeOverrides` (currently agent resolution is outside the override system)
- Fix `from_launch_request()` to preserve `approval="default"` as a real value (violation #7)
- No structural changes needed — the `resolve()` function is already correct

### `resolve.py` — Core refactor
- **Delete** the ad-hoc if/elif chain in `resolve_policies()` for model/harness
- **Add** `derive_harness()` function: takes resolved model + resolved harness + config, returns final HarnessId
- **Refactor** `resolve_policies()` signature: accept the full list of `RuntimeOverrides` layers instead of a pre-merged `overrides` parameter
- Move config default model into the layer stack (it belongs in `config_overrides`, not as a post-hoc fallback)

### `plan.py` / `prepare.py` — Caller simplification
- Delete the split between `pre_resolved` and `resolved` — there's only one resolution pass now
- Profile loading moves before `resolve_policies()` (it already effectively does, but the flow becomes clearer)
- Config overrides participate in model/harness resolution (fixing violations #1, #2, #3)

### `settings.py` — No changes
- pydantic-settings source ordering is already correct
- `default_model_for_harness()` still needed for the derivation phase

## Key Design Decisions

### Agent field in RuntimeOverrides
Agent resolution currently lives outside the override system. Adding it to `RuntimeOverrides` means the same first-non-None mechanism handles agent precedence, eliminating violation #4 (`primary.agent` being dead).

**Config agent reconciliation**: Two config fields exist — `config.primary_agent` (top-level, default `"__meridian-orchestrator"`) and `config.primary.agent` (nested, default `None`). `from_config()` reads `config.primary.agent`. The builtin default agent is passed separately as a function argument (not a layer), so the existing `config.primary_agent` default still works as the fallback when no layer sets agent. `config.primary.agent` becomes a user-settable override at config precedence level.

### Config default model as a layer vs. fallback
Currently `config.default_model` is applied as a post-hoc fallback after harness resolution. In the new design, `RuntimeOverrides.from_config()` already reads `config.primary.model` — we just need to ensure the harness default model (`config.default_model_for_harness()`) is also accessible. This goes into the derivation phase, not the layer stack, because it depends on the resolved harness (a derived field).

### Approval "default" sentinel
`from_launch_request` currently maps `approval="default"` to `None`, making it invisible. **Deferred** — fixing requires changing the CLI argument parser default, which is outside scope. See decision D4.

### Harness and model are independent fields

**Correction from user review**: The original design assumed `-m` should override the harness. That's wrong. Harness and model resolve independently through the precedence chain. Harness derivation from model is a **fallback** that only kicks in when no layer specifies a harness at all.

The resolution is simple:
```
harness = first_non_none(subcommand, profile.harness, config.harness) or derive_from(resolved_model) or default
model   = first_non_none(cli.model, env.model, profile.model, config.model) or default_for(harness)
```

Then validate compatibility — if the combination is truly impossible (e.g., running a model on a harness that doesn't support its provider), error. But many "mismatched" combinations are valid (e.g., sonnet on opencode works fine — opencode supports anthropic models).

Examples:
- `meridian codex -m sonnet` → explicit harness via subcommand + explicit model → respect both, validate compat
- `meridian spawn -a reviewer -m sonnet` (profile has `harness: opencode`) → profile harness + CLI model → try sonnet on opencode
- `meridian spawn -m sonnet` (no harness anywhere) → derive harness from model → claude

This means `derive_harness()` does NOT need to be layer-aware. Standard first-non-None resolution works for harness, with model-derived harness as the final fallback.

### Remove `--harness` flag from spawn

The `--harness` flag on `meridian spawn` is redundant with harness subcommands (`meridian codex`, `meridian claude`, `meridian opencode`). Two ways to set the same thing is confusing. Remove it.

Harness is set by:
1. Subcommand (`meridian codex`) — explicit user intent, always wins
2. Profile — respected unless incompatible with resolved model
3. Derived from model — fallback when nothing else specifies harness
4. Config default

### Harness-model compatibility validation
Validation happens once, after both harness and model are independently resolved. If the combination is truly incompatible (harness doesn't support the model's provider at all), error with a clear message. Many cross-provider combinations work (opencode supports multiple providers) — don't over-restrict.

## What This Doesn't Change

- `MeridianConfig` and pydantic-settings loading — already correct
- `RuntimeOverrides` field set and validation — already correct  
- How skills are resolved — orthogonal to precedence
- How permissions/approval are applied — downstream of resolution
- The `ResolvedPolicies` return type — same shape, different internals

## Migration

This is internal refactoring with one CLI-facing change: removal of `--harness` flag from `meridian spawn`. No config format changes, no profile format changes. Existing tests should pass (or fail in ways that reveal they were testing buggy behavior). New tests should verify:

1. `-m sonnet` on an opencode-profiled agent runs sonnet on opencode (not claude)
2. `meridian codex -m sonnet` respects both explicit harness and model
3. `-m sonnet` with no harness anywhere derives claude harness
4. `config.primary.model` actually takes effect when no CLI/env/profile model is set
5. `config.primary.agent` participates in agent resolution
6. Config default harness is used when no model or harness is specified anywhere
