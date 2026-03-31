# Phase 1c: Background Worker Plan Persistence (R4)

## Scope

Replace the manual argv serialization pattern in `execute.py`'s background worker with disk-based persistence. Currently, every continuation field requires hand-coded argv serialization + parser argument + deserialization. Adding `source_execution_cwd` (Phase 3) would be yet another field in this fragile chain.

After this phase, the background worker command is just `--spawn-id` and `--repo-root`. All other parameters are loaded from a JSON file in the spawn log directory. New fields added to the persisted model automatically flow through.

## Files to Modify

### `src/meridian/lib/ops/spawn/execute.py`

#### 1. Define `BackgroundWorkerParams` model

Add a Pydantic model near the top of the module (after existing model definitions):

```python
class BackgroundWorkerParams(BaseModel):
    """Parameters for background worker execution, persisted to disk."""

    model_config = ConfigDict(frozen=True)

    timeout: float | None = None
    skills: tuple[str, ...] = ()
    agent_name: str | None = None
    mcp_tools: tuple[str, ...] = ()
    permission_tier: str | None = None
    approval: str = "default"
    allowed_tools: tuple[str, ...] = ()
    passthrough_args: tuple[str, ...] = ()
    continue_harness_session_id: str | None = None
    continue_fork: bool = False
    session_agent: str = ""
    session_agent_path: str = ""
    session_skill_paths: tuple[str, ...] = ()
    adhoc_agent_payload: str = ""
    appended_system_prompt: str | None = None
    autocompact: int | None = None
    forked_from_chat_id: str | None = None
```

#### 2. Add persistence helpers

```python
_BG_WORKER_PARAMS_FILENAME = "bg-worker-params.json"


def _persist_bg_worker_params(log_dir: Path, params: BackgroundWorkerParams) -> None:
    """Write background worker params to the spawn log directory."""
    params_path = log_dir / _BG_WORKER_PARAMS_FILENAME
    atomic_write_text(params_path, params.model_dump_json(indent=2) + "\n")


def _load_bg_worker_params(log_dir: Path) -> BackgroundWorkerParams:
    """Load background worker params from the spawn log directory."""
    params_path = log_dir / _BG_WORKER_PARAMS_FILENAME
    return BackgroundWorkerParams.model_validate_json(params_path.read_text(encoding="utf-8"))
```

#### 3. Update `_build_background_worker_command()`

Simplify to just pass spawn_id and repo_root:

```python
def _build_background_worker_command(
    *,
    spawn_id: str,
    repo_root: Path,
) -> tuple[str, ...]:
    return (
        sys.executable,
        "-m",
        "meridian.lib.ops.spawn.execute",
        "--spawn-id",
        spawn_id,
        "--repo-root",
        repo_root.as_posix(),
    )
```

#### 4. Update `execute_spawn_background()`

After `_init_spawn` and `_write_params_json`, persist worker params:

```python
bg_params = BackgroundWorkerParams(
    timeout=payload.timeout,
    skills=prepared.skills,
    agent_name=prepared.agent_name,
    mcp_tools=prepared.mcp_tools,
    permission_tier=(
        prepared.execution.permission_config.tier.value
        if prepared.execution.permission_config.tier is not None
        else None
    ),
    approval=prepared.execution.permission_config.approval,
    allowed_tools=prepared.execution.allowed_tools,
    passthrough_args=prepared.passthrough_args,
    continue_harness_session_id=prepared.session.harness_session_id,
    continue_fork=prepared.session.continue_fork,
    session_agent=prepared.session_agent,
    session_agent_path=prepared.session_agent_path,
    session_skill_paths=prepared.skill_paths,
    adhoc_agent_payload=prepared.adhoc_agent_payload,
    appended_system_prompt=prepared.appended_system_prompt,
    autocompact=prepared.autocompact,
    forked_from_chat_id=payload.forked_from_chat_id,
)
_persist_bg_worker_params(log_dir, bg_params)
```

Update `_build_background_worker_command` call to pass only `spawn_id` and `repo_root`.

#### 5. Update `_build_background_worker_parser()`

Simplify to only parse spawn_id and repo_root:

```python
def _build_background_worker_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m meridian.lib.ops.spawn.execute")
    parser.add_argument("--spawn-id", required=True)
    parser.add_argument("--repo-root", required=True)
    return parser
```

#### 6. Update `_background_worker_main()`

Load params from disk instead of parsing argv:

```python
def _background_worker_main(
    argv: Sequence[str] | None = None,
    *,
    ctx: RuntimeContext | None = None,
) -> int:
    resolved_context = runtime_context(ctx)
    parser = _build_background_worker_parser()
    parsed = parser.parse_args(list(argv) if argv is not None else None)

    repo_root = Path(parsed.repo_root).expanduser().resolve()
    spawn_id = SpawnId(parsed.spawn_id)
    log_dir = resolve_spawn_log_dir(repo_root, spawn_id)
    params = _load_bg_worker_params(log_dir)

    permission_config, permission_resolver = resolve_permission_pipeline(
        sandbox=params.permission_tier,
        allowed_tools=params.allowed_tools,
        approval=params.approval,
    )
    return asyncio.run(
        _execute_existing_spawn(
            spawn_id=spawn_id,
            repo_root=repo_root,
            timeout=params.timeout,
            skills=params.skills,
            agent_name=params.agent_name,
            mcp_tools=params.mcp_tools,
            permission_config=permission_config,
            permission_resolver=permission_resolver,
            allowed_tools=params.allowed_tools,
            passthrough_args=params.passthrough_args,
            continue_harness_session_id=params.continue_harness_session_id,
            continue_fork=params.continue_fork,
            session_agent=params.session_agent,
            session_agent_path=params.session_agent_path,
            session_skill_paths=params.session_skill_paths,
            adhoc_agent_payload=params.adhoc_agent_payload,
            appended_system_prompt=params.appended_system_prompt,
            autocompact=params.autocompact,
            forked_from_chat_id=params.forked_from_chat_id,
            ctx=resolved_context,
        )
    )
```

## Dependencies

- **Requires**: Nothing -- purely restructures execute.py internals.
- **Produces**: Disk-based param persistence with `BackgroundWorkerParams` model. Downstream phases extend it:
  - Phase 2a adds `execution_cwd: str | None = None`
  - Phase 3 adds `source_execution_cwd: str | None = None`
  - Both automatically flow through without touching argv or parser.

## Patterns to Follow

- Use `atomic_write_text` for persistence (already imported in execute.py).
- Use `model_dump_json` / `model_validate_json` for Pydantic serialization (consistent with other models in the codebase).
- Place `bg-worker-params.json` alongside `params.json` in the spawn log dir.

## Constraints

- The background worker subprocess is spawned with `start_new_session=True` -- it runs detached. The JSON file must be written BEFORE the subprocess is spawned.
- Log dir is created by `_init_spawn` (via `start_spawn` -> mkdir). Verify it exists before writing.
- Do NOT change `_execute_existing_spawn()`'s signature -- it's called by both background worker and foreground path. Phase 2a modifies it.
- Keep `--spawn-id` and `--repo-root` as argv -- they're needed to locate the params file.
- The `_parse_csv_skills()` helper is no longer needed for background worker argv parsing. Keep it if used elsewhere, remove if not.

## Verification Criteria

- [ ] `uv run ruff check .` passes
- [ ] `uv run pyright` passes (0 errors)
- [ ] `uv run pytest-llm` passes
- [ ] `BackgroundWorkerParams` model exists and includes all fields from old argv
- [ ] `_build_background_worker_command()` only passes `--spawn-id` and `--repo-root`
- [ ] `_build_background_worker_parser()` only parses `--spawn-id` and `--repo-root`
- [ ] `execute_spawn_background()` writes `bg-worker-params.json` before spawning subprocess
- [ ] `_background_worker_main()` loads params from disk
- [ ] All fields from old argv are present in `BackgroundWorkerParams`
