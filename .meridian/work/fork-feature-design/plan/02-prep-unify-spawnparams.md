# Phase Prep 2: Unify SpawnParams Construction in plan.py

## Scope

Extract a shared SpawnParams builder in `resolve_primary_launch_plan()` to eliminate the two divergent construction sites. Currently the MERIDIAN_HARNESS_COMMAND override path (line ~218) and the normal path (line ~289) independently construct `SpawnParams` with slightly different field sets. New fields (like `continue_fork` for fork) would need adding in both places — error-prone and already divergent (the override path doesn't set `appended_system_prompt`).

## Intent

After this phase, there's one SpawnParams construction point. Fork 5 adds `continue_fork` in exactly one place.

## Files to Modify

- **`src/meridian/lib/launch/plan.py`** — Extract a `_build_run_params()` helper that takes the common fields and returns `SpawnParams`. Both paths call this helper, then the normal path enriches with `appended_system_prompt`. The MERIDIAN_HARNESS_COMMAND path may override `extra_args` differently.

## Dependencies

- **Requires**: Prep 1 (SessionMode is available on LaunchRequest, used by the builder).
- **Produces**: Single SpawnParams construction site that Fork 5 extends.

## Interface Contract

```python
def _build_run_params(
    *,
    prompt: str,
    model: ModelId | None,
    thinking: str | None,
    skills: tuple[str, ...],
    agent: str | None,
    adhoc_agent_payload: str,
    extra_args: tuple[str, ...],
    repo_root: str,
    mcp_tools: tuple[str, ...],
    continue_harness_session_id: str | None,
    appended_system_prompt: str | None = None,
    report_output_path: str | None = None,
) -> SpawnParams:
    """Build SpawnParams for primary launch. Single construction site."""
```

The exact signature may vary — the goal is that both code paths call this with their respective values, and new fields only need adding once.

## Patterns to Follow

- Look at the existing two construction sites in `plan.py` lines 218-230 and 289-302. The helper should capture all shared fields and let callers pass the divergent ones.
- Keep `interactive=True` always (this is the primary launch builder).

## Constraints

- Do NOT change the external behavior of `resolve_primary_launch_plan()`. The `ResolvedPrimaryLaunchPlan` output must be identical.
- Do NOT add fork-related fields yet. Just unify construction.
- The MERIDIAN_HARNESS_COMMAND path should still reject fork (it won't know about fork yet — that's Fork 5).

## Verification Criteria

- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes with 0 errors
- [ ] `uv run pytest-llm` passes
- [ ] `uv run meridian --dry-run` produces identical output to before
- [ ] Only ONE `SpawnParams(` constructor call exists in `plan.py` (inside the helper)
- [ ] Both MERIDIAN_HARNESS_COMMAND and normal paths produce correct SpawnParams
