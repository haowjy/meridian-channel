# Phase 3.2: Primary CLI Expansion

## Scope

Add `--sandbox`, `--thinking`, `--approval`, `--timeout`, `--budget`, `--max-turns`, and `--skills` flags to the primary CLI entry point (`meridian` root command and harness shortcuts). Update `LaunchRequest` to carry these values.

## Why

These flags already exist on `meridian spawn` but are missing from the primary launch command. Users can't specify sandbox mode, thinking budget, or timeout when launching a primary session.

## Files to Modify

### `src/meridian/lib/launch/types.py`

Add fields to `LaunchRequest`:

```python
class LaunchRequest(BaseModel):
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
    # New fields:
    sandbox: str | None = None
    thinking: str | None = None
    timeout: float | None = None        # minutes
    budget: float | None = None          # USD
    max_turns: int | None = None
    skills: tuple[str, ...] = ()
```

### `src/meridian/cli/main.py`

#### 1. `root()` function (lines 261-329)

Add these parameters to the `root()` function signature:

```python
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
thinking: Annotated[
    str | None,
    Parameter(
        name="--thinking",
        help="Thinking budget: low, medium, high, xhigh.",
    ),
] = None,
approval: Annotated[
    str | None,
    Parameter(
        name="--approval",
        help="Approval mode: default, confirm, auto, yolo.",
    ),
] = None,
timeout: Annotated[
    float | None,
    Parameter(
        name="--timeout",
        help="Maximum session runtime in minutes.",
    ),
] = None,
budget: Annotated[
    float | None,
    Parameter(
        name="--budget",
        help="Maximum spend in USD for this session.",
    ),
] = None,
max_turns: Annotated[
    int | None,
    Parameter(
        name="--max-turns",
        help="Maximum conversation turns.",
    ),
] = None,
skills: Annotated[
    str | None,
    Parameter(
        name="--skills",
        help="Comma-separated skills to load for the primary agent.",
    ),
] = None,
```

Handle `--yolo` / `--approval` mutual exclusion (same logic as in spawn.py):

```python
if yolo and approval is not None:
    raise ValueError("Cannot use --yolo with --approval.")
resolved_approval = approval if approval is not None else ("yolo" if yolo else "default")
```

Pass all new fields to `_run_primary_launch()`.

#### 2. `_run_primary_launch()` function (lines 460-552)

Update signature to accept the new parameters and build `LaunchRequest` with them:

```python
def _run_primary_launch(
    *,
    continue_ref: str | None,
    model: str,
    harness: str | None,
    agent: str | None,
    work: str,
    yolo: bool,
    autocompact: int | None,
    dry_run: bool,
    passthrough: tuple[str, ...],
    # New:
    sandbox: str | None = None,
    thinking: str | None = None,
    approval: str = "default",
    timeout: float | None = None,
    budget: float | None = None,
    max_turns: int | None = None,
    skills: tuple[str, ...] = (),
) -> None:
```

Update `LaunchRequest` construction:

```python
launch_result = launch_primary(
    repo_root=repo_root,
    request=LaunchRequest(
        model=model,
        harness=continue_harness if resume_target else harness,
        agent=agent,
        work_id=work.strip() or None,
        autocompact=autocompact,
        passthrough_args=passthrough,
        fresh=fresh,
        pinned_context="",
        dry_run=dry_run,
        approval=resolved_approval,
        continue_harness_session_id=continue_harness_session_id,
        continue_chat_id=continue_chat_id,
        # New:
        sandbox=sandbox,
        thinking=thinking,
        timeout=timeout,
        budget=budget,
        max_turns=max_turns,
        skills=skills,
    ),
    harness_registry=harness_registry,
)
```

#### 3. Harness shortcut commands (`_register_harness_shortcut_command`, lines 555-639)

Add matching parameters to each shortcut function and pass through to `_run_primary_launch()`. The shortcuts should mirror the root command's full parameter set.

#### 4. Top-level flag registrations (lines 735-765)

Add new flags to `_TOP_LEVEL_VALUE_FLAGS`:

```python
_TOP_LEVEL_VALUE_FLAGS = frozenset({
    "--format", "--config", "--continue", "--model", "--harness",
    "--agent", "-a", "--work", "--autocompact",
    # New:
    "--sandbox", "--thinking", "--approval", "--timeout",
    "--budget", "--max-turns", "--skills",
})
```

#### 5. Parse `--skills` as CSV

Use the same `_parse_csv_list` helper from `spawn.py`, or extract it to a shared location. The `--skills` flag takes a comma-separated string and produces a `tuple[str, ...]`.

## Dependencies

- Requires Phase 3.1 (config fields must exist in PrimaryConfig for Phase 3.3 to wire them)
- Does NOT need to read config values yet — that's Phase 3.3

## Interface Contract

After this phase, `LaunchRequest` carries all seven new fields. The CLI parses and validates them. But the launch pipeline does NOT yet use the new fields from config as fallbacks — that wiring happens in Phase 3.3.

## Constraints

- Do NOT wire config fallbacks (e.g., `config.primary.sandbox`) into runtime resolution yet
- Do NOT change the spawn CLI — it already has these flags
- Skills must be comma-separated (same as spawn --skills)
- --yolo and --approval remain mutually exclusive
- Budget is in USD, timeout is in minutes (match spawn CLI)

## Verification Criteria

- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes
- [ ] `uv run pytest-llm` passes
- [ ] `uv run meridian --help` shows the new flags
- [ ] `uv run meridian --dry-run --sandbox full-access` produces a valid dry-run output
- [ ] `uv run meridian --dry-run --thinking high --approval auto` works
- [ ] `uv run meridian --dry-run --skills "plan-implementation,review"` works
