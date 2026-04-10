# Transport Projections

## Purpose

Define how each harness-specific launch spec becomes transport wire data. Projections are shared by subprocess and streaming paths where possible, and guarded so field drift fails at import time.

## Projection Modules

```text
src/meridian/lib/harness/projections/
  _guards.py
  project_claude.py
  project_codex_subprocess.py
  project_codex_streaming.py
  project_opencode_subprocess.py
  project_opencode_streaming.py
```

Naming invariant: one module per `(harness, transport)` conceptual thing.

## Guard Helper

All projection modules call a shared helper:

```python
# src/meridian/lib/harness/projections/_guards.py
def _check_projection_drift(
    spec_cls: type[BaseModel],
    projected: frozenset[str],
    delegated: frozenset[str],
) -> None:
    expected = set(spec_cls.model_fields)
    accounted = projected | delegated
    if expected != accounted:
        missing = expected - accounted
        stale = accounted - expected
        raise ImportError(
            f"{spec_cls.__name__} projection drift. "
            f"missing={sorted(missing)} stale={sorted(stale)}"
        )
```

Each module executes `_check_projection_drift(...)` at import time.

Unit tests exercise `_check_projection_drift` directly with synthetic spec classes for:

- happy path
- missing field
- stale field

No monkey-patching `model_fields` is required.

## Claude Projection (`project_claude.py`)

```python
_PROJECTED_FIELDS: frozenset[str] = frozenset({
    "model",
    "effort",
    "agent_name",
    "appended_system_prompt",
    "agents_payload",
    "continue_session_id",
    "continue_fork",
    "permission_resolver",
    "extra_args",
    "prompt",
    "interactive",
})

_DELEGATED_FIELDS: frozenset[str] = frozenset()

_check_projection_drift(ClaudeLaunchSpec, _PROJECTED_FIELDS, _DELEGATED_FIELDS)
```

`project_claude_spec_to_cli_args(spec, base_command=...)` maintains one canonical order and one `--allowedTools` dedupe pass.

Policy for `--append-system-prompt` collisions: Meridian-managed flag appears in canonical position; user passthrough copy remains later in tail; user wins by last-wins behavior. Projection emits a warning when known managed flags appear in `extra_args`.

## Codex Subprocess Projection (`project_codex_subprocess.py`)

Post-D15, `CodexLaunchSpec` fields are:

- base `ResolvedLaunchSpec` fields
- `report_output_path`

No `sandbox_mode` or `approval_mode` field exists on the spec.

```python
_PROJECTED_FIELDS: frozenset[str] = frozenset({
    "model",
    "effort",
    "prompt",
    "continue_session_id",
    "continue_fork",
    "permission_resolver",
    "extra_args",
    "interactive",
    "report_output_path",
})

_DELEGATED_FIELDS: frozenset[str] = frozenset()

_check_projection_drift(CodexLaunchSpec, _PROJECTED_FIELDS, _DELEGATED_FIELDS)
```

Command projection reads permissions through resolver flags and applies reserved-flag filtering to passthrough args before append.

## Codex Streaming Projection (`project_codex_streaming.py`)

This module replaces `codex_appserver.py` + `codex_jsonrpc.py` and exports:

- `project_codex_spec_to_appserver_command(...)`
- `project_codex_spec_to_thread_request(...)`

### Field Accounting Pattern (transport-wide)

Transport-wide completeness is enforced by the union of all consumers in the streaming path, not only one projection function.

Each consumer module exports `_ACCOUNTED_FIELDS`.

```python
# project_codex_streaming.py
_APP_SERVER_ACCOUNTED_FIELDS: frozenset[str] = frozenset({
    "permission_resolver",
    "extra_args",
    # delegated to artifact extraction, not app-server wire
    "report_output_path",
})

_JSONRPC_ACCOUNTED_FIELDS: frozenset[str] = frozenset({
    "model",
    "effort",
})

_METHOD_SELECTION_ACCOUNTED_FIELDS: frozenset[str] = frozenset({
    "continue_session_id",
    "continue_fork",
})

_PROMPT_SENDER_ACCOUNTED_FIELDS: frozenset[str] = frozenset({
    "prompt",
})

_ENV_ACCOUNTED_FIELDS: frozenset[str] = frozenset({
    "interactive",
})

_SPEC_DELEGATED_FIELDS: frozenset[str] = frozenset({
    "report_output_path",
})

_ACCOUNTED_FIELDS = (
    _APP_SERVER_ACCOUNTED_FIELDS
    | _JSONRPC_ACCOUNTED_FIELDS
    | _METHOD_SELECTION_ACCOUNTED_FIELDS
    | _PROMPT_SENDER_ACCOUNTED_FIELDS
    | _ENV_ACCOUNTED_FIELDS
)

if not _SPEC_DELEGATED_FIELDS <= _ACCOUNTED_FIELDS:
    missing_consumers = _SPEC_DELEGATED_FIELDS - _ACCOUNTED_FIELDS
    raise ImportError(
        f"Codex streaming delegated fields have no consumer: {sorted(missing_consumers)}"
    )

_check_projection_drift(
    CodexLaunchSpec,
    projected=_ACCOUNTED_FIELDS - _SPEC_DELEGATED_FIELDS,
    delegated=_SPEC_DELEGATED_FIELDS,
)
```

A field listed as delegated in one function must still appear in at least one consumer `_ACCOUNTED_FIELDS` set across the transport.

### App-Server Command Example

```python
def project_codex_spec_to_appserver_command(
    spec: CodexLaunchSpec,
    *,
    host: str,
    port: int,
) -> list[str]:
    command = ["codex", "app-server", "--listen", f"ws://{host}:{port}"]

    sandbox = spec.permission_resolver.config.sandbox
    if sandbox and sandbox != "default":
        command.extend(("-c", f'sandbox_mode="{sandbox}"'))

    approval = spec.permission_resolver.config.approval
    policy = _map_approval_to_codex_policy(approval)
    if policy is not None:
        command.extend(("-c", f'approval_policy="{policy}"'))

    if spec.report_output_path is not None:
        logger.debug(
            "Codex streaming ignores report_output_path; reports extracted from artifacts",
            path=spec.report_output_path,
        )

    filtered_extra = _strip_reserved_passthrough(
        spec.extra_args,
        reserved=_RESERVED_CODEX_ARGS,
        harness="codex",
    )
    if filtered_extra:
        logger.debug("Forwarding passthrough args to codex app-server", extra_args=list(filtered_extra))
        command.extend(filtered_extra)

    return command
```

## OpenCode Subprocess Projection (`project_opencode_subprocess.py`)

Projects CLI args for `opencode run`. `permission_resolver` is consumed via env projection, not CLI flags.

## OpenCode Streaming Projection (`project_opencode_streaming.py`)

Exports both:

- `project_opencode_spec_to_session_payload(...)`
- `project_opencode_spec_to_serve_command(...)`

Passthrough debug logging lives in `project_opencode_spec_to_serve_command` (not session payload).

## Reserved Flags Policy

Projection modules strip reserved passthrough args and emit warning logs per stripped arg.

- Codex reserved args: `sandbox`, `sandbox_mode`, `approval_policy`, `full-auto`, `ask-for-approval`
- Claude reserved args: `--allowedTools`, `--disallowedTools` (merged/deduped, not overridden)

## Codex Approval Semantics

The matrix requirement is semantic behavior and auditability, not unique wire strings for every cell. Wire values may collapse (`auto`/`yolo`/`confirm` all mapping to `on-request`) while Meridian-side handling and logs distinguish behavior.

## Interaction with Other Docs

- [launch-spec.md](launch-spec.md): authoritative spec fields.
- [permission-pipeline.md](permission-pipeline.md): resolver config type and strict policy.
- [typed-harness.md](typed-harness.md): dispatch guard and generic contracts.
