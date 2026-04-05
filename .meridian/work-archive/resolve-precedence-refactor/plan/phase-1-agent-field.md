# Phase 1: Add `agent` field to RuntimeOverrides

## Scope

Add an `agent: str | None = None` field to `RuntimeOverrides` so agent resolution can use the same first-non-None mechanism as all other fields. Update all factory methods to populate it where appropriate.

This is a purely additive change. No existing behavior changes. The `agent` field won't be consumed by `resolve_policies()` until Phase 3.

## Files to Modify

### `src/meridian/lib/core/overrides.py`

1. **Add field** to `RuntimeOverrides`:
   ```python
   agent: str | None = None
   ```
   Place it after `harness` and before `effort` (logical grouping: identity fields first, then behavior fields).

2. **Update `from_launch_request()`** — read `request.agent`:
   ```python
   agent=_normalize_optional_string(request.agent),
   ```

3. **Update `from_env()`** — read `MERIDIAN_AGENT`:
   ```python
   agent=_read_env_string("MERIDIAN_AGENT"),
   ```

4. **Update `from_config()`** — read `config.primary.agent`:
   ```python
   agent=primary.agent if hasattr(primary, 'agent') else None,
   ```
   Note: Check whether `primary.agent` exists on the `PrimaryConfig` model. If it does, read it directly. If not, this stays `None` and the config-level agent comes from `config.primary_agent` via a different path (Phase 3 will wire this up).

5. **Update `from_spawn_input()`** — read `payload.agent`:
   ```python
   agent=_normalize_optional_string(payload.agent),
   ```

6. **Update `from_agent_profile()`** — do NOT set agent. The profile IS the agent; it doesn't override itself:
   ```python
   # agent intentionally not set — profile doesn't override agent selection
   ```

## Dependencies

- None. This is a leaf change.

## Interface Contract

After this phase, `RuntimeOverrides` has an `agent` field that participates in `resolve()` first-non-None merge. The field is populated from CLI, env, config, and spawn input layers. It is NOT yet consumed by resolution logic (that's Phase 3).

## Verification Criteria

- [ ] `uv run pyright` passes (0 errors)
- [ ] `uv run ruff check .` passes
- [ ] `uv run pytest-llm` passes (existing tests still work)
- [ ] Manual check: `RuntimeOverrides(agent="foo").agent == "foo"`
- [ ] Manual check: `resolve(RuntimeOverrides(agent="a"), RuntimeOverrides(agent="b")).agent == "a"`
- [ ] Manual check: `resolve(RuntimeOverrides(), RuntimeOverrides(agent="b")).agent == "b"`

## Agent Staffing

- 1 coder (default model)
- 2 reviewers: 1 on default model (correctness focus), 1 on a different model (design alignment with design/overview.md)
- 1 verifier
