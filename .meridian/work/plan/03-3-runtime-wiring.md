# Phase 3.3: Runtime Resolution Wiring

## Scope

Wire the new config TOML fields and primary CLI flags through the runtime resolution pipeline so that the full precedence chain works: `ENV > CLI > YAML profile > Config > harness default`. This affects both the primary launch path and the spawn path.

## Why

Phases 3.1 and 3.2 added the fields to config and CLI, but they're not connected yet. The launch pipeline still reads `sandbox` and `thinking` only from the agent profile, ignoring config defaults. The primary CLI's new flags aren't forwarded to the harness command builder.

## Files to Modify

### `src/meridian/lib/launch/plan.py` — Primary launch resolution

The `resolve_primary_launch_plan()` function (lines 114-313) currently:

1. **sandbox** (line 244-245): Only reads `profile.sandbox`. Must also consider `request.sandbox` (CLI) and `config.primary.sandbox` (config TOML).

2. **thinking** (lines 214, 286): Only reads `profile.thinking`. Must also consider `request.thinking` (CLI) and `config.primary.thinking` (config TOML).

3. **approval** (line 248): Reads `request.approval` — already wired from CLI. Must also consider `config.primary.approval` as fallback, AND `profile.approval` in the chain.

4. **timeout**: Not currently used in primary launch. The new `request.timeout` field needs to be available for execution policy (or passthrough).

5. **budget** / **max_turns**: Not currently in the launch path. The new `request.budget` and `request.max_turns` fields need to be available for harness adapter passthrough.

6. **skills**: Not currently in primary launch CLI. The new `request.skills` field needs to be merged with profile skills (same as spawn path).

#### Specific changes in `resolve_primary_launch_plan()`:

**Sandbox resolution** — Replace direct `profile.sandbox` usage:
```python
# Precedence: CLI > Config > Profile
resolved_sandbox = (
    request.sandbox
    or resolved_config.primary.sandbox
    or (profile.sandbox if profile is not None else None)
)

permission_config, resolver = resolve_permission_pipeline(
    sandbox=resolved_sandbox,
    allowed_tools=profile.tools if profile is not None else (),
    approval=resolved_approval,
)
```

**Thinking resolution** — Replace direct `profile.thinking` usage:
```python
# Precedence: CLI > Config > Profile
resolved_thinking = (
    request.thinking
    or resolved_config.primary.thinking
    or (profile.thinking if profile is not None else None)
)
# Use resolved_thinking in SpawnParams instead of profile.thinking
```

**Approval resolution** — Add config fallback:
```python
# Precedence: CLI (request.approval) > Config > Profile > "default"
resolved_approval = request.approval
if resolved_approval == "default":
    resolved_approval = (
        resolved_config.primary.approval
        or (profile.approval if profile is not None else None)
        or "default"
    )
```

**Skills resolution** — Merge CLI skills with profile skills:
```python
# Merge profile skills with ad-hoc CLI --skills, deduplicating
if request.skills:
    merged_skill_names = dedupe_skill_names(
        (*resolved_skills.skill_names, *request.skills)
    )
    resolved_skills = resolve_skills_from_profile(
        profile_skills=merged_skill_names,
        repo_root=resolved_root,
        readonly=True,
    )
```

**Autocompact resolution** — Add config fallback (currently missing for primary path):
```python
resolved_autocompact = (
    request.autocompact
    or (profile.autocompact if profile is not None else None)
    or resolved_config.primary.autocompact
)
```

### `src/meridian/lib/ops/spawn/prepare.py` — Spawn resolution

The `build_create_payload()` function already resolves sandbox/thinking/approval from CLI + profile, but it's missing config fallback. Add config as the middle layer.

**Lines 291-294 (sandbox)**:
```python
resolved_sandbox = (
    payload.sandbox
    or resolved_config.primary.sandbox   # NEW: config fallback
    or (profile.sandbox if profile is not None else None)
)
```

Wait — for spawns, config defaults should only apply if the spawn doesn't have its own profile value. The precedence should be: `CLI > Profile > Config > harness default`. This is different from primary launch where it's `CLI > Config > Profile` because profiles are the agent-specific override.

Actually, re-reading the design spec precedence:
```
ENV > CLI > YAML profile > Project Config > User Config > harness default
```

So for spawns: `ENV > SpawnCLI > Profile > Config`. Profile wins over config.

For primary launch: `ENV > PrimaryCLI > Profile > Config`. Same ordering.

So the config fallback should be AFTER profile, not before:

```python
resolved_sandbox = (
    payload.sandbox                                        # CLI
    or (profile.sandbox if profile is not None else None)  # Profile
    or runtime_view.config.primary.sandbox                 # Config
)
```

Update prepare.py lines 291-294, 309-311, and 295-303 (approval) to add config as the last fallback before "default".

**Timeout wiring** — In `build_create_payload()`, the timeout is already read from `payload.timeout`. Add config fallback:

```python
resolved_timeout = payload.timeout or runtime_view.config.primary.timeout
# Use resolved_timeout instead of payload.timeout for ExecutionPolicy
```

### `src/meridian/lib/launch/resolve.py` — No changes needed

The `resolve_policies()` function handles model/harness/agent/skills resolution. sandbox/thinking/approval/timeout resolution happens at the call site (plan.py/prepare.py), not in resolve_policies. No changes needed here.

## Dependencies

- Requires Phase 3.2 (CLI flags and LaunchRequest fields must exist)
- Requires Phase 2 (autocompact rename must be done so we reference `config.primary.autocompact` not `autocompact_pct`)

## Interface Contract

After this phase, the full precedence chain works for all universal fields:

| Field | ENV | CLI | Profile | Config | Default |
|-------|-----|-----|---------|--------|---------|
| sandbox | `MERIDIAN_SANDBOX` → config | `--sandbox` | profile.sandbox | config.primary.sandbox | None |
| thinking | `MERIDIAN_THINKING` → config | `--thinking` | profile.thinking | config.primary.thinking | None |
| approval | `MERIDIAN_APPROVAL` → config | `--approval` | profile.approval | config.primary.approval | "default" |
| timeout | `MERIDIAN_TIMEOUT` → config | `--timeout` | — | config.primary.timeout | None |
| autocompact | via config | `--autocompact` | profile.autocompact | config.primary.autocompact | None |

Note: ENV flows through config (loaded at settings.py level), so ENV > Config is handled by the config loading precedence already.

## Constraints

- Precedence order must be: ENV > CLI > Profile > Config > harness default
- Do NOT change the approval semantics for `--yolo` — it's shorthand for `--approval yolo`
- Do NOT change how `tools` and `mcp_tools` are resolved (YAML-only)
- `timeout` is in minutes everywhere (CLI, config, internal)
- Budget and max_turns wiring in primary launch may require changes to harness adapters to pass through — if adapters don't support these fields, log a warning and skip

## Verification Criteria

- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes
- [ ] `uv run pytest-llm` passes
- [ ] Primary launch with `--sandbox workspace-write --dry-run` shows sandbox in output command
- [ ] Spawn with config `primary.sandbox = "workspace-write"` uses it when no CLI override
- [ ] CLI `--sandbox` overrides config `primary.sandbox`
- [ ] Profile sandbox overrides config sandbox (when no CLI override)
- [ ] Config sandbox is used when neither CLI nor profile specifies it
