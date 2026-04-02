# Phase 1: Atomic Removal — Install Module, Callers, CLI, and Tests

## Why atomic
Phase 1 (old) deleted `lib/install/` and Phase 2 (old) removed its callers. Between phases, dangling imports break pyright/ruff/runtime. All three reviewers flagged this. Merge into one atomic phase.

## Scope
Delete `src/meridian/lib/install/`, `src/meridian/cli/install_cmd.py`, all imports/callers of the install module across the codebase, and all install-related tests. After this phase, zero references to `meridian.lib.install` remain.

## Steps

### 1. Delete install module
- Delete entire `src/meridian/lib/install/` directory (11 files + `__init__.py`)

### 2. Delete install CLI
- Delete `src/meridian/cli/install_cmd.py`

### 3. Remove CLI registration in `src/meridian/cli/main.py`
- Remove `sources` from the help text (~line 59)
- Remove `sources_app = App(name="sources", ...)` (~line 450)
- Remove `app.command(sources_app, name="sources")` (~line 465)
- Remove `from meridian.cli.install_cmd import register_sources_commands` import (~line 856)
- Remove `register_sources_commands(sources_app, emit)` call (~line 868)

### 4. Remove bootstrap from launch path

#### `src/meridian/lib/launch/resolve.py`
- Remove imports: `BootstrapPlan`, `ensure_bootstrap_assets`, `plan_bootstrap_assets`, `planned_bootstrap_agent_names` from `meridian.lib.install.bootstrap`
- Remove `ensure_bootstrap_ready()` function entirely (~lines 80-104)
- Remove `ensure_bootstrap_ready` from `__all__`

#### `src/meridian/lib/launch/plan.py`
- Remove import: `resolve_runtime_asset_provenance` from `meridian.lib.install.provenance` (line 15)
- Remove import: `ensure_bootstrap_ready` from `.resolve` (line 25)
- Remove the `bootstrap_plan = ensure_bootstrap_ready(...)` call block (~line 171)
- Remove the `runtime_provenance = resolve_runtime_asset_provenance(...)` call block (~line 220)
- Update `_build_session_metadata()` call: stop passing `profile_source`, `skill_sources`, `bootstrap_required_items`, `bootstrap_missing_items` (lines 228-235)

#### `src/meridian/lib/ops/spawn/prepare.py`
- Remove import: `resolve_runtime_asset_provenance` from `meridian.lib.install.provenance` (line 17)
- Remove import: `ensure_bootstrap_ready` from launch resolve (line 25)
- Remove the `bootstrap_plan = ensure_bootstrap_ready(...)` call block (~line 199)
- Remove the `runtime_provenance = resolve_runtime_asset_provenance(...)` call block (~line 367)
- Update downstream: stop passing `agent_source`, `skill_sources`, `bootstrap_required_items`, `bootstrap_missing_items` (lines 380-383)

### 5. Delete install tests
- Delete entire `tests/lib/install/` directory (6 test files + `__init__.py`)
- In `tests/ops/test_spawn_prepare_fork.py`: remove the `monkeypatch` of `meridian.lib.ops.spawn.prepare.ensure_bootstrap_ready` (line 18) and update the test to work without it

### 6. Delete install smoke test
- Delete `tests/smoke/install/install-cycle.md` (entire file — tests `meridian sources install/update/uninstall/status`)

## Verification
- `uv run ruff check .` — no import errors
- `uv run pyright` — no type errors
- `uv run pytest-llm` — all remaining tests pass
- `uv run meridian --help` — `sources` no longer appears
- `uv run meridian spawn --dry-run -m sonnet -p "test"` — launch path works without bootstrap
