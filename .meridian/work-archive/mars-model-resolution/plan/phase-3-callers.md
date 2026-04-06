# Phase 3: Callers — Update resolve.py, registry.py, ops/catalog.py

## Scope

Update all callers of `route_model()` to use `resolve_model()` instead. Simplify `_derive_harness_from_model()` and `resolve_harness()` in resolve.py. Update `HarnessRegistry.route()` direct mode.

## Files to Modify

- `src/meridian/lib/launch/resolve.py` — simplify 3 functions, remove `route_model` import
- `src/meridian/lib/harness/registry.py` — update direct mode in `route()`, remove `route_model` import
- `src/meridian/lib/ops/catalog.py` — replace `route_model` call with `resolve_model`

## What to Build

### `resolve.py` — Three simplifications

**1. `_derive_harness_from_model()` (line 181)** — collapse to single call:

```python
def _derive_harness_from_model(model_str: str, *, repo_root: Path) -> HarnessId:
    """Derive harness from model when no layer specifies harness."""
    from meridian.lib.catalog.models import resolve_model as resolve_model_entry

    resolved = resolve_model_entry(model_str, repo_root=repo_root)
    return resolved.harness
```

Remove the `try/except` fallback to `route_model` — `resolve_model()` now handles all fallback cases internally.

**2. `resolve_harness()` (line 136)** — remove `route_model` fallback:

```python
def resolve_harness(
    *,
    model: ModelId,
    harness_override: str | None,
    harness_registry: HarnessRegistry,
    repo_root: Path,
) -> HarnessId:
    warning: str | None = None
    from meridian.lib.catalog.models import resolve_model

    resolved = resolve_model(str(model), repo_root=repo_root)
    routed_harness_id = resolved.harness
    # ... rest of compatibility check unchanged (lines 152-178)
```

Remove the `try/except ValueError` that falls back to `route_model()`. `resolve_model()` already raises ValueError if nothing matches, which is the correct behavior.

**3. Remove the top-level import** of `route_model` (line 9):

```python
# REMOVE this line:
from meridian.lib.catalog.models import route_model
```

The lazy imports inside functions (`from meridian.lib.catalog.models import resolve_model`) are already there and stay.

### `registry.py` — Update direct mode

Line 109 uses `route_model` for direct mode:
```python
decision = route_model(model=model, mode=mode)
return self.get_in_process_harness(decision.harness_id), decision.warning
```

Replace with direct `HarnessId.DIRECT`:
```python
return self.get_in_process_harness(HarnessId.DIRECT), None
```

Remove the top-level import of `route_model` (line 8). The harness mode branch (line 103-107) already uses `resolve_model` via lazy import and doesn't need `route_model`.

### `ops/catalog.py` — Replace route_model call

Line 219:
```python
harness = route_model(model_id, repo_root=repo_root).harness_id
```

Replace with:
```python
from meridian.lib.catalog.models import resolve_model
# ...
harness = resolve_model(model_id, repo_root=repo_root).harness
```

Update the import block: remove `route_model` from the import list at line 20, add `resolve_model` if not already imported.

## Dependencies

- Requires: Phase 2 (`resolve_model()` rewritten)
- Independent of: Phase 4

## Constraints

- `resolve_harness()` signature and return type don't change
- `_derive_harness_from_model()` signature and return type don't change
- `resolve_policies()` is not modified — it calls `_derive_harness_from_model()` which is simplified
- `HarnessRegistry.route()` overload signatures don't change

## Verification Criteria

- [ ] `uv run pyright` passes
- [ ] `uv run ruff check .` passes
- [ ] `uv run pytest-llm` passes
- [ ] No remaining imports of `route_model` in these 3 files
- [ ] `grep -r "route_model" src/meridian/lib/launch/resolve.py src/meridian/lib/harness/registry.py src/meridian/lib/ops/catalog.py` returns nothing
