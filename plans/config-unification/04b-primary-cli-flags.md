# Step 4b: Primary CLI Flags

## Scope

Add missing RuntimeOverrides CLI flags to the primary launch command (`meridian`, `meridian claude`, `meridian codex`, `meridian opencode`) so all applicable tuning knobs are settable from the primary CLI. Currently only `--model`, `--harness`, `--yolo`, and `--autocompact` exist on primary.

## Files to Modify

- `src/meridian/lib/launch/types.py` — add fields to `LaunchRequest`
- `src/meridian/cli/main.py` — add CLI flags to `root()` and `_register_harness_shortcut_command()`
- `src/meridian/lib/core/overrides.py` — update `from_launch_request()` for new fields

## Dependencies

- **Requires**: Step 3 (resolution wired — so new CLI fields flow through resolve()).
- **Independent of**: Step 4a (config TOML expansion — different files).
- **Produces**: All applicable RuntimeOverrides fields settable via primary CLI.

## What to Change

### 1. Expand `LaunchRequest` in types.py

Add missing fields:
```python
class LaunchRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: str = ""
    harness: str | None = None
    agent: str | None = None
    work_id: str | None = None
    fresh: bool = False
    autocompact: int | None = None
    passthrough_args: tuple[str, ...] = ()
    pinned_context: str = ""
    dry_run: bool = False
    approval: str = "default"
    continue_harness_session_id: str | None = None
    continue_chat_id: str | None = None
    # NEW fields:
    thinking: str | None = None
    sandbox: str | None = None
    timeout: float | None = None
```

**Do NOT add `budget` or `max_turns`** — per design spec, these have no real consumers in the primary launch pipeline yet. Adding CLI flags for dead fields is misleading.

### 2. Add CLI flags to `root()` in main.py

Add to the `root()` function parameters:

```python
thinking: Annotated[
    str | None,
    Parameter(
        name="--thinking",
        help="Thinking budget: low, medium, high, xhigh.",
    ),
] = None,
sandbox: Annotated[
    str | None,
    Parameter(
        name="--sandbox",
        help=(
            "Sandbox mode: read-only, workspace-write, full-access, "
            "danger-full-access, unrestricted."
        ),
    ),
] = None,
approval: Annotated[
    str | None,
    Parameter(
        name="--approval",
        help="Approval mode: default, confirm, auto, yolo. Overrides agent profile.",
    ),
] = None,
timeout: Annotated[
    float | None,
    Parameter(
        name="--timeout",
        help="Maximum runtime in minutes.",
    ),
] = None,
```

**Approval / yolo interaction**: Currently `root()` has `yolo: bool` and resolves `resolved_approval = "yolo" if yolo else "default"`. With `--approval` added:
- Add the same mutual-exclusion check as spawn: `if yolo and approval is not None: raise ValueError(...)`
- `resolved_approval = approval if approval is not None else ("yolo" if yolo else "default")`

Wire new params through `_run_primary_launch()`:
```python
_run_primary_launch(
    continue_ref=continue_ref,
    model=model,
    harness=harness,
    agent=agent,
    work=work,
    yolo=yolo,
    approval=approval,       # NEW
    thinking=thinking,       # NEW
    sandbox=sandbox,         # NEW
    timeout=timeout,         # NEW
    autocompact=autocompact,
    dry_run=dry_run,
    passthrough=passthrough,
)
```

Update `_run_primary_launch()` signature and the `LaunchRequest` construction:
```python
launch_result = launch_primary(
    repo_root=repo_root,
    request=LaunchRequest(
        model=model,
        harness=continue_harness if resume_target is not None else harness,
        agent=agent,
        work_id=work.strip() or None,
        autocompact=autocompact,
        thinking=thinking,           # NEW
        sandbox=sandbox,             # NEW
        timeout=timeout,             # NEW
        approval=resolved_approval,
        # ... rest unchanged
    ),
    harness_registry=harness_registry,
)
```

### 3. Add CLI flags to `_register_harness_shortcut_command()` in main.py

The harness shortcut function (claude, codex, opencode) needs the same flags. Add matching parameters:

```python
thinking: Annotated[str | None, Parameter(name="--thinking", help="...")] = None,
sandbox: Annotated[str | None, Parameter(name="--sandbox", help="...")] = None,
approval: Annotated[str | None, Parameter(name="--approval", help="...")] = None,
timeout: Annotated[float | None, Parameter(name="--timeout", help="...")] = None,
```

And wire them through to `_run_primary_launch()`.

### 4. Update `_run_primary_launch()` signature

Add the new parameters and pass them through to LaunchRequest:
```python
def _run_primary_launch(
    *,
    continue_ref: str | None,
    model: str,
    harness: str | None,
    agent: str | None,
    work: str,
    yolo: bool,
    approval: str | None,    # NEW
    thinking: str | None,    # NEW
    sandbox: str | None,     # NEW
    timeout: float | None,   # NEW
    autocompact: int | None,
    dry_run: bool,
    passthrough: tuple[str, ...],
) -> None:
```

### 5. Update `from_launch_request()` in overrides.py

```python
@classmethod
def from_launch_request(cls, request: LaunchRequest) -> "RuntimeOverrides":
    return cls(
        model=request.model or None,
        harness=request.harness,
        thinking=request.thinking,
        sandbox=request.sandbox,
        approval=request.approval if request.approval != "default" else None,
        autocompact=request.autocompact,
        timeout=request.timeout,
    )
```

### 6. Update `_TOP_LEVEL_VALUE_FLAGS` in main.py

Add new flags to the set so the argv parser handles them correctly:
```python
_TOP_LEVEL_VALUE_FLAGS = frozenset({
    "--format", "--config", "--continue", "--model", "--harness",
    "--agent", "-a", "--work", "--autocompact",
    "--thinking", "--sandbox", "--approval", "--timeout",  # NEW
})
```

## Patterns to Follow

- `src/meridian/cli/spawn.py` for CLI flag style (Annotated parameters with Parameter)
- Existing `--yolo` / `--approval` interaction pattern in spawn.py

## Constraints

- Do NOT add `--budget` or `--max-turns` — no consumers in primary pipeline.
- Do NOT change config TOML parsing (that's Step 4a).
- Keep `--yolo` as shorthand for `--approval yolo`.
- Keep backward compatibility: existing CLI usage unchanged.

## Verification Criteria

- [ ] `uv run pyright` passes with 0 errors
- [ ] `uv run ruff check .` passes
- [ ] `uv run pytest-llm` passes
- [ ] `uv run meridian --help` shows --thinking, --sandbox, --approval, --timeout
- [ ] `uv run meridian claude --help` shows the same new flags
- [ ] `uv run meridian --dry-run --thinking high` includes thinking in launch plan
- [ ] `uv run meridian --dry-run --approval auto` works (and --yolo still works)
- [ ] `uv run meridian --yolo --approval auto` raises error (mutual exclusion)
- [ ] `uv run meridian --dry-run --sandbox full-access` works
- [ ] `uv run meridian --dry-run --timeout 30` works
