# Phase 1e: Codex Arg Ordering with Pre-Subcommand Flag Support (R6 + Phase 5)

## Scope

Fix Codex resume command construction so permission flags (sandbox, approval modes) appear before the `resume` subcommand. Rather than bypassing `build_harness_command()`, extend it with a `subcommand` parameter that allows callers to specify args that go after global flags but before extra_args. This gives Codex resume correct ordering while keeping all command construction in one place.

This phase is **completely independent** of Phases 1a-4 and can run in parallel with any of them.

## Files to Modify

### `src/meridian/lib/harness/common.py`

Add a `subcommand` parameter to `build_harness_command()`:

```python
def build_harness_command(
    *,
    base_command: tuple[str, ...],
    subcommand: tuple[str, ...] = (),   # NEW: inserted after permissions, before extra_args
    prompt_mode: PromptMode,
    run: SpawnParams,
    strategies: StrategyMap,
    perms: PermissionResolver,
    harness_id: HarnessId,
    mcp_config: McpConfig | None = None,
) -> list[str]:
```

Insert `subcommand` into the output after permission flags and MCP config, but before extra_args/prompt:

```python
    command = list(base_command)
    if prompt_mode is PromptMode.FLAG and run.prompt:
        command.append(run.prompt)
    command.extend(strategy_args)
    permission_flags = perms.resolve_flags(harness_id)
    command.extend(permission_flags)
    if mcp_config is not None:
        command.extend(mcp_config.command_args)
    command.extend(subcommand)              # NEW LINE
    if prompt_mode is PromptMode.POSITIONAL:
        command.extend(run.extra_args)
        if run.prompt:
            command.append(run.prompt)
        return command
    command.extend(run.extra_args)
    return command
```

Result ordering: `base_command + prompt(FLAG) + strategies + permissions + mcp + subcommand + extra_args + prompt(POSITIONAL)`

When `subcommand` is empty (default), behavior is identical to current code.

### `src/meridian/lib/harness/codex.py`

Update `build_command()` to use `subcommand` for resume paths.

**Non-interactive resume path** (current lines 347-361):

Replace the current approach of putting `resume <id>` in `base_command`:

```python
if harness_session_id:
    # Resume: keep base_command as prefix, put resume in subcommand
    # so permission flags land between them (Codex requires global flags
    # before subcommands).
    resume_subcommand = ("resume", harness_session_id)
    command_run = run.model_copy(update={"prompt": "-"})
    if run.report_output_path:
        command_run = command_run.model_copy(
            update={
                "extra_args": (*command_run.extra_args, "-o", run.report_output_path),
            },
        )
    return build_harness_command(
        base_command=self.BASE_COMMAND,         # ("codex", "exec", "--json")
        subcommand=resume_subcommand,           # ("resume", session_id)
        prompt_mode=self.PROMPT_MODE,
        run=command_run,
        strategies=self.STRATEGIES,
        perms=perms,
        harness_id=self.id,
    )
```

Result: `codex exec --json [strategies] [permissions] resume <id> [-o report.md] [passthrough] -`

Strategies are all DROP for resume (existing behavior), so effectively: `codex exec --json [permissions] resume <id> [-o report.md] [passthrough] -`

**Interactive resume path** (current lines 329-345):

```python
if run.interactive:
    harness_session_id = (run.continue_harness_session_id or "").strip()
    if harness_session_id:
        resume_subcommand = ("resume", harness_session_id)
        guarded_prompt = run.prompt
        command_run = (
            run.model_copy(update={"prompt": guarded_prompt})
            if guarded_prompt != run.prompt
            else run
        )
        return build_harness_command(
            base_command=self.PRIMARY_BASE_COMMAND,  # ("codex",)
            subcommand=resume_subcommand,            # ("resume", session_id)
            prompt_mode=self.PROMPT_MODE,
            run=command_run,
            strategies=self.STRATEGIES,
            perms=perms,
            harness_id=self.id,
        )
    # Fresh interactive path unchanged...
```

Result: `codex [strategies] [permissions] resume <id> [extra_args] [prompt]`

**Fresh session paths**: No change. `subcommand` defaults to empty tuple.

## Dependencies

- **Requires**: Nothing -- fully independent.
- **Produces**: Correct Codex resume command with global flags before subcommand.
- **Independent of**: All other phases.

## Interface Contract

```python
def build_harness_command(
    *,
    base_command: tuple[str, ...],
    subcommand: tuple[str, ...] = (),   # NEW
    prompt_mode: PromptMode,
    run: SpawnParams,
    strategies: StrategyMap,
    perms: PermissionResolver,
    harness_id: HarnessId,
    mcp_config: McpConfig | None = None,
) -> list[str]
```

## Patterns to Follow

- Other harness adapters (Claude, OpenCode) don't use `subcommand` -- they pass it as the default empty tuple (or don't pass it at all).
- Verify that existing callers of `build_harness_command` don't break -- the new parameter has a default value.

## Constraints

- `subcommand` defaults to `()` -- all existing callers are unaffected without changes.
- Permission flags come from `perms.resolve_flags(self.id)` -- do not duplicate resolution logic.
- Strategy-mapped flags (model, thinking) are intentionally present for resume (Codex strategies use `DROP` for resume-irrelevant fields). The strategies handle this.
- For interactive resume, the `DO NOT DO ANYTHING` guard is NOT applied (existing behavior: guard is only for fresh sessions).
- `run.extra_args` and prompt ordering MUST match the existing fresh-session pattern (POSITIONAL mode).

## Verification Criteria

- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes (0 errors)
- [ ] `uv run pytest-llm` passes
- [ ] Non-interactive resume produces: `codex exec --json <permission_flags> resume <id> [-o report.md] [extra_args] -`
- [ ] Interactive resume produces: `codex <permission_flags> resume <id> [extra_args] [prompt]`
- [ ] Fresh session paths (no harness_session_id) are unchanged
- [ ] Claude adapter's `build_command()` works without changes (doesn't pass `subcommand`)
- [ ] `build_harness_command()` signature is backward-compatible (new param has default)
