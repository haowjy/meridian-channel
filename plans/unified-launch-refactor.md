# Unified Agent Launch Refactor

**Status:** done

## Problem

`meridian start` (interactive, user-driven) and `meridian run spawn` (programmatic, LLM-driven) do the same thing — launch an agent — but have:

1. **Different input models**: `SpaceStartInput` vs `RunCreateInput` with different fields for the same concepts
2. **Different code paths**: `launch.py` vs `_run_execute.py` with duplicated agent/skill resolution, materialization, session management, and command building
3. **Different flag sets**: `start` is missing `--agent`, `--permission`, `--timeout-secs`, `--budget-*`, `--unsafe`, `--guardrail`, `--secret`
4. **SRP violations**: `launch.py` mixes space lifecycle, agent resolution, command building, materialization, session management, and process execution
5. **`--skills` still exists**: Should have been removed — agent profiles own skills statically (see WHAT-TO-REMOVE.md §1.1)

## Step 0: Remove `--skills` CLI flag (prerequisite, independent)

Agent profiles own skills statically. The `--skills` flag allows per-run skill overrides which contradicts the design. Remove it.

### Files to change

#### `src/meridian/cli/run.py`
- **Remove** `skill_flags` parameter (lines 50-57)
- **Remove** `skills=skill_flags` from `RunCreateInput()` (line 155)
- **Remove** the `KeyError` handler for `unknown_skills` (lines 175-182) — with no CLI skills, unknown-skill errors can't happen from user input
- Keep emit/exit_code logic intact

#### `src/meridian/lib/ops/_run_models.py`
- **Remove** `skills: tuple[str, ...] = ()` from `RunCreateInput` (line 22)
- Keep `skills` on `RunActionOutput` (line 59) — that reports which skills the run used (from agent profile)

#### `src/meridian/lib/ops/_run_prepare.py`
- **Remove** `_normalize_skill_flags()` function (lines 84-93) — dead code
- **Change** line 236: `explicit_requested_skills = ()` (or just remove the variable)
- **Change** line 237: `requested_skills = ()` (always empty — skills come from profile only)
- **Remove** lines 295-300: unknown explicit skills KeyError (no explicit skills possible)
- **Update** line 270 comment: remove mention of `--skills`
- The call to `resolve_run_defaults(payload.model, requested_skills, ...)` now always passes `()` for `requested_skills`

#### `src/meridian/lib/prompt/assembly.py`
- **Simplify** `resolve_run_defaults`: `requested_skills` parameter can be removed or defaulted to `()`
- **Simplify** merge logic (lines 61-65): no CLI skills to prepend — just use `profile.skills` directly
- Keep `RunPromptDefaults.skills` — it holds the agent profile's skills

#### `src/meridian/lib/prompt/assembly.py` (signature change)
All callers of `resolve_run_defaults` need updating:
- `_run_prepare.py` line 273-276
- `launch.py` line 169-173

#### Tests
- `tests/test_cli_ux_fixes.py` — remove `--skills` flag tests
- `tests/test_flag_strategy.py` — remove `--skills` validation tests  
- Any test constructing `RunCreateInput(skills=...)` — remove the `skills=` kwarg
- Run full suite to find breakage

### What stays
- `skills` field on internal types (`_PreparedCreate`, `RunParams`, `RunActionOutput`, `SessionRecord`, etc.) — these track agent-profile-declared skills through the pipeline
- Skill loading, composition, and materialization — unchanged, just no longer user-overridable
- The ad-hoc agent JSON logic in `_run_prepare.py` — it handles extra skills beyond agent's declared set, which could still happen if the agent profile has skills not in the repo

## Step 1: Add `--agent` + shared flags to `meridian start`

After `--skills` is removed, add the flags that SHOULD be shared:

### New flags on `meridian start`

| Flag | Type | Notes |
|------|------|-------|
| `--agent` / `-a` | `str \| None` | Override default primary agent profile |
| `--permission` | `str \| None` | Permission tier |
| `--unsafe` | `bool` | Allow unsafe execution |
| `--timeout-secs` | `float \| None` | Session timeout |
| `--budget-per-run-usd` | `float \| None` | Per-run budget cap |
| `--budget-per-space-usd` | `float \| None` | Space budget cap |
| `--guardrail` | `tuple[str, ...]` | Guardrails |
| `--secret` | `tuple[str, ...]` | Secret keys |

### Plumbing

1. Add fields to `SpaceStartInput` and `SpaceResumeInput`
2. Add fields to `SpaceLaunchRequest`
3. Thread through `launch_primary()` → `_build_interactive_command()`
4. Use `--agent` to override `config.default_primary_agent` in `_build_interactive_command`

## Step 2: Extract shared `AgentLaunchConfig` (deeper refactor)

**Goal**: Single dataclass for "how to launch an agent" used by both paths.

```python
@dataclass(frozen=True, slots=True)
class AgentLaunchConfig:
    model: str = ""
    agent: str | None = None
    # No --skills. Agent profiles own skills statically.
    permission_tier: str | None = None
    unsafe: bool = False
    timeout_secs: float | None = None
    budget_per_run_usd: float | None = None
    budget_per_space_usd: float | None = None
    guardrails: tuple[str, ...] = ()
    secrets: tuple[str, ...] = ()
    dry_run: bool = False
```

Both `SpaceLaunchRequest` and `RunCreateInput` compose this.

## Step 3: Extract shared `resolve_launch()` pipeline

Currently duplicated in `launch.py._build_interactive_command` and `_run_prepare._build_create_payload`:
- Agent profile loading
- Skill resolution from agent profile
- Model routing + harness detection
- Materialization
- Permission resolution

Extract to: `src/meridian/lib/launch_resolve.py`

## Step 4: Simplify execution layers

- `launch.py` → thin: space lifecycle + `resolve_launch()` + Popen
- `_run_execute.py` → thin: depth/budget checks + `resolve_launch()` + spawn

## Implementation Order

| Step | Risk | Dependencies | Can do now? |
|------|------|-------------|-------------|
| 0: Remove `--skills` | Low | None | ✅ |
| 1: Add shared flags to `start` | Low | Step 0 | ✅ after Step 0 |
| 2: Extract `AgentLaunchConfig` | Medium | Steps 0-1 | After 0-1 pass |
| 3: Extract `resolve_launch()` | Medium | Step 2 | Sequential |
| 4: Simplify execution | Medium | Step 3 | Sequential |

**Recommend**: Steps 0-1 now (immediate value), Steps 2-4 as a focused batch.
