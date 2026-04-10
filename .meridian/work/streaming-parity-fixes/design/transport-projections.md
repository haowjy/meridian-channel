# Transport Projections

## Purpose

Specify how each `ResolvedLaunchSpec` subclass becomes the wire-format bytes a harness actually receives. Every projection is a **shared function** that both the subprocess runner and the streaming runner call — no per-transport duplication, no per-transport arg ordering divergence. Every projection module declares a `_PROJECTED_FIELDS` frozenset and runs an **import-time completeness check** that fails with `ImportError` if the spec gains a field the projection forgot.

This doc resolves H1 (Codex sandbox/approval dropped), H2 (duplicate `--allowedTools` in Claude streaming), H4 (D15 guard missing), M3 (arg ordering divergence), M4 (OpenCode skills double-injection), and M7 (missing passthrough-args debug log).

## Where Projections Live

```
src/meridian/lib/harness/projections/
    __init__.py           — re-exports
    claude.py             — project_claude_spec_to_cli_args(spec)
    codex_cli.py          — project_codex_spec_to_cli_args(spec)  (subprocess)
    codex_appserver.py    — project_codex_spec_to_appserver(spec) (streaming)
    codex_jsonrpc.py      — project_codex_spec_to_thread_request(spec)
    opencode_cli.py       — project_opencode_spec_to_cli_args(spec)  (subprocess)
    opencode_http.py      — project_opencode_spec_to_session_payload(spec)
```

Each projection is a pure function. It never reads environment variables, never checks process state, never calls subprocess, never touches the filesystem. The only input is the spec subclass; the only output is the projected structure. Pure functions are trivially unit-testable and produce reproducible diffs when specs change.

## Claude Projection — Shared by Subprocess and Streaming

Claude subprocess and streaming share the same executable (`claude`) with different flags. The spec-derived arguments are identical. Only the base command prefix differs.

```python
# src/meridian/lib/harness/projections/claude.py
from meridian.lib.harness.launch_spec import ClaudeLaunchSpec
from meridian.lib.core.types import HarnessId

SUBPROCESS_BASE: tuple[str, ...] = ("claude", "-")
STREAMING_BASE: tuple[str, ...] = (
    "claude",
    "-p",
    "--input-format", "stream-json",
    "--output-format", "stream-json",
    "--verbose",
)

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

def project_claude_spec_to_cli_args(
    spec: ClaudeLaunchSpec,
    *,
    base_command: tuple[str, ...],
) -> list[str]:
    """Project a ClaudeLaunchSpec to its CLI command list.

    base_command is either SUBPROCESS_BASE or STREAMING_BASE.
    All spec-derived ordering is identical across both transports.
    Called by ClaudeAdapter.build_command() and ClaudeConnection.start().
    """
    command: list[str] = list(base_command)

    # 1. Model
    if spec.model:
        command.extend(("--model", spec.model))

    # 2. Effort (already normalized by factory)
    if spec.effort:
        command.extend(("--effort", spec.effort))

    # 3. Agent profile
    if spec.agent_name:
        command.extend(("--agent", spec.agent_name))

    # 4. Append-system-prompt (skill injection)
    if spec.appended_system_prompt:
        command.extend(("--append-system-prompt", spec.appended_system_prompt))

    # 5. Ad-hoc agents payload
    if spec.agents_payload:
        command.extend(("--agents", spec.agents_payload))

    # 6. Resume / fork
    if spec.continue_session_id:
        command.extend(("--resume", spec.continue_session_id))
        if spec.continue_fork:
            command.append("--fork-session")

    # 7. Permission flags from resolver
    perm_flags = list(spec.permission_resolver.resolve_flags(HarnessId.CLAUDE))

    # 8. Extra args from caller
    extra = list(spec.extra_args)

    # 9. Merge + dedupe — H2 resolution.
    # Both perm_flags and extra may contain --allowedTools; the shared
    # dedupe pass collapses them into one flag with the union.
    merged = _merge_allowed_tools(perm_flags, extra)
    command.extend(merged)

    return command


# Import-time completeness check — H4 / D15 resolution.
_actual = set(ClaudeLaunchSpec.model_fields)
if _actual != _PROJECTED_FIELDS:
    missing = _actual - _PROJECTED_FIELDS
    extra = _PROJECTED_FIELDS - _actual
    raise ImportError(
        f"ClaudeLaunchSpec projection drift. Missing from _PROJECTED_FIELDS: "
        f"{missing}. Stale: {extra}. Update "
        f"src/meridian/lib/harness/projections/claude.py."
    )
```

The `_merge_allowed_tools` helper is the single H2 fix:

```python
def _merge_allowed_tools(*arg_lists: list[str]) -> list[str]:
    """Merge argument lists, collapsing duplicate --allowedTools into
    one deduped flag. Preserves argument order except for the single
    merged --allowedTools flag, which is appended at the end of the
    last list that contained it."""
    combined: list[str] = []
    collected_tools: list[str] = []
    for args in arg_lists:
        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "--allowedTools":
                if i + 1 < len(args):
                    collected_tools.extend(_split_csv(args[i + 1]))
                    i += 2
                    continue
                i += 1
                continue
            if arg.startswith("--allowedTools="):
                collected_tools.extend(_split_csv(arg.split("=", 1)[1]))
                i += 1
                continue
            combined.append(arg)
            i += 1
    if collected_tools:
        deduped = _dedupe_preserving_order(collected_tools)
        combined.extend(("--allowedTools", ",".join(deduped)))
    return combined
```

Both `_split_csv` and `_dedupe_preserving_order` live in `src/meridian/lib/launch/text_utils.py` (L4: generic utilities that don't belong in `claude_preflight.py`).

### Canonical Arg Ordering — M3 Resolution

The v1 subprocess and streaming paths emitted Claude args in different orders:

| # | v1 subprocess | v1 streaming |
|---|---|---|
| 1 | `--model` | `--model` |
| 2 | `--effort` | `--effort` |
| 3 | `--agent` | `--agent` |
| 4 | perm_flags | `--append-system-prompt` |
| 5 | extra_args | `--agents` |
| 6 | `--append-system-prompt` | `--resume` / `--fork-session` |
| 7 | `--agents` | perm_flags |
| 8 | `--resume` / `--fork-session` | extra_args |

The v2 canonical order (single projection function, same for both transports):

| # | Canonical |
|---|---|
| 1 | `--model` |
| 2 | `--effort` |
| 3 | `--agent` |
| 4 | `--append-system-prompt` |
| 5 | `--agents` |
| 6 | `--resume` / `--fork-session` |
| 7 | merged perm_flags + extra_args (with `--allowedTools` deduped) |

Rationale for the order:
- Identity/execution flags first (`--model`, `--effort`, `--agent`) — easy to grep for, first in command logs.
- Prompt-shaping flags next (`--append-system-prompt`, `--agents`) — affect what Claude sees before it sees user input.
- Session-continuity flags next (`--resume`, `--fork-session`) — tell Claude to reconnect.
- Permission and passthrough flags last — with deduped `--allowedTools`.

**Extra-args duplication policy (E22).** If `extra_args` contains a flag Meridian also emits (e.g., `--append-system-prompt`), Meridian's value appears first (in its canonical position) and the user's passthrough version appears later in the merged tail. Claude's last-wins semantics mean the user's value wins. This matches subprocess v1 behavior and is documented. A projection-time warning is logged when a known flag is detected in `extra_args`.

Parity test asserts this ordering: given an identical `ClaudeLaunchSpec`, both `project_claude_spec_to_cli_args(spec, base_command=SUBPROCESS_BASE)` and `project_claude_spec_to_cli_args(spec, base_command=STREAMING_BASE)` produce byte-identical arg lists from position `len(base_command)` onward.

## Codex Projection — Three Functions

Codex has three distinct wire formats: subprocess CLI (`codex exec --json`), streaming launch CLI (`codex app-server --listen ws://...`), and streaming JSON-RPC session bootstrap (`sendUserTurn` / `startThread` params). Each has its own projection function.

### Codex Subprocess CLI

```python
# src/meridian/lib/harness/projections/codex_cli.py
_PROJECTED_FIELDS: frozenset[str] = frozenset({
    "model", "effort", "sandbox_mode", "approval_mode", "prompt",
    "continue_session_id", "continue_fork", "permission_resolver",
    "extra_args", "interactive", "report_output_path",
})

def project_codex_spec_to_cli_args(spec: CodexLaunchSpec) -> list[str]:
    """codex exec --json CLI arguments."""
    command = ["codex"]
    if spec.continue_session_id:
        command.extend(("resume", spec.continue_session_id))
    else:
        command.append("exec")
    command.append("--json")

    if spec.model:
        command.extend(("--model", spec.model))
    if spec.effort:
        command.extend(("-c", f'model_reasoning_effort="{spec.effort}"'))

    # Permission flags from resolver (handles --sandbox, --full-auto,
    # -c approval_policy, etc.)
    command.extend(spec.permission_resolver.resolve_flags(HarnessId.CODEX))

    # Report output path — Codex-only subprocess feature
    if spec.report_output_path:
        command.extend(("-o", spec.report_output_path))

    command.extend(spec.extra_args)
    command.append("-")  # stdin prompt mode
    return command
```

Note: the subprocess path's sandbox/approval reach the wire via `spec.permission_resolver.resolve_flags(HarnessId.CODEX)` — which reads `permission_resolver.config.sandbox` and `.approval` via the Protocol property (no getattr fallback). The projection itself does not read `spec.sandbox_mode` / `spec.approval_mode` because those are streaming-specific semantic values mapped in `codex.py:_map_sandbox_mode` / `_map_approval_mode`. To keep the completeness guard truthful, the subprocess projection explicitly lists these fields as "consumed via permission_resolver" (see below).

Actually, the cleaner shape: `sandbox_mode` and `approval_mode` are **redundantly encoded** — they appear on the spec for streaming's benefit, but their authoritative source is `permission_resolver.config`. To avoid storing the same semantic value twice, the design is simpler:

**Revised shape: sandbox/approval modes are NOT stored on `CodexLaunchSpec`.** The streaming projection reads them directly from `spec.permission_resolver.config.sandbox` and `.approval` — the same source the subprocess path uses. One authoritative location, no duplicate state.

```python
class CodexLaunchSpec(ResolvedLaunchSpec):
    """Codex-specific resolved launch spec."""
    report_output_path: str | None = None
```

The streaming projection maps semantic permission config → Codex app-server flags and JSON-RPC params, documented below. This removes a field from the spec, simplifies the mental model (one permission source of truth), and still resolves H1 because the projection is the one doing the reading — previously no projection read these fields at all.

**Re-checking H1 under this revised shape:** `codex_ws.py` currently ignores `sandbox_mode` / `approval_mode`. Under v2, the new `project_codex_spec_to_appserver()` and `project_codex_spec_to_thread_request()` functions read `spec.permission_resolver.config.sandbox` / `.approval` and project them to the wire. The security downgrade is fixed at the projection site where it belongs.

### Codex Streaming — App-Server Launch CLI

```python
# src/meridian/lib/harness/projections/codex_appserver.py
_PROJECTED_FIELDS: frozenset[str] = frozenset({
    "model", "effort", "prompt", "continue_session_id", "continue_fork",
    "permission_resolver", "extra_args", "interactive", "report_output_path",
})

def project_codex_spec_to_appserver_command(
    spec: CodexLaunchSpec,
    *,
    host: str,
    port: int,
) -> list[str]:
    """Arguments for `codex app-server --listen ws://host:port ...`.

    Projects sandbox and approval_policy from the permission resolver
    config into -c overrides. This resolves H1 — the streaming path
    now honors sandbox/approval settings.
    """
    command = [
        "codex", "app-server",
        "--listen", f"ws://{host}:{port}",
    ]

    # Sandbox — H1 fix
    sandbox = spec.permission_resolver.config.sandbox
    if sandbox and sandbox != "default":
        command.extend(("-c", f'sandbox_mode="{sandbox}"'))

    # Approval policy — H1 fix
    approval = spec.permission_resolver.config.approval
    codex_policy = _map_approval_to_codex_policy(approval)
    if codex_policy:
        command.extend(("-c", f'approval_policy="{codex_policy}"'))

    # Passthrough args — M7 debug log
    if spec.extra_args:
        logger.debug(
            "Forwarding passthrough args to codex app-server",
            extra_args=list(spec.extra_args),
        )
        command.extend(spec.extra_args)

    return command


def _map_approval_to_codex_policy(mode: str) -> str | None:
    """Map Meridian approval modes to Codex approval_policy values."""
    # "default" → Codex's default policy → omit
    # "auto" / "yolo" → "on-request" + auto-accept in request handler
    # "confirm" → "on-request" with reject in request handler
    return {
        "default": None,
        "auto": "on-request",
        "yolo": "on-request",
        "confirm": "on-request",
    }.get(mode)
```

The exact Codex config key names (`sandbox_mode`, `approval_policy`) must be verified against the real `codex app-server --help` output before the @coder lands this — see the integration-boundary discipline in [edge-cases.md](edge-cases.md). If Codex exposes these as CLI flags rather than `-c` overrides, the projection flattens accordingly.

### Codex Streaming — JSON-RPC Thread Bootstrap

```python
# src/meridian/lib/harness/projections/codex_jsonrpc.py
_PROJECTED_FIELDS: frozenset[str] = frozenset({
    "model", "effort", "prompt", "continue_session_id", "continue_fork",
    "permission_resolver", "extra_args", "interactive", "report_output_path",
})

def project_codex_spec_to_thread_request(
    spec: CodexLaunchSpec,
) -> dict[str, object]:
    """Projected params for the codex app-server startThread JSON-RPC call."""
    params: dict[str, object] = {}
    if spec.model:
        params["model"] = spec.model
    if spec.effort:
        params.setdefault("config", {})
        cast(dict[str, object], params["config"])["model_reasoning_effort"] = spec.effort
    return params
```

`extra_args` on JSON-RPC is a no-op (the wire format has no passthrough channel at the thread-request layer). The projection lists it in `_PROJECTED_FIELDS` but a comment explains it is consumed by the app-server launch projection instead. This is how the completeness guard handles fields that have multiple projection targets across a single transport.

Actually, to keep the guard honest, the cleaner shape is: each projection function has its own `_PROJECTED_FIELDS` naming only the fields it reads, and a **sibling set** `_DELEGATED_TO_APPSERVER_COMMAND` (or similar) explicitly names fields that are consumed by a partner projection. The guard then asserts `_PROJECTED_FIELDS | _DELEGATED | _IGNORED == set(Spec.model_fields)`.

```python
# codex_jsonrpc.py
_PROJECTED_FIELDS: frozenset[str] = frozenset({"model", "effort"})
_DELEGATED_FIELDS: frozenset[str] = frozenset({
    "prompt",               # sent via sendUserTurn, not thread bootstrap
    "continue_session_id",  # affects method choice (thread/resume vs thread/start)
    "continue_fork",        # affects method choice (thread/fork)
    "permission_resolver",  # projected to app-server command
    "extra_args",           # projected to app-server command
    "interactive",          # streaming is never interactive; ignored
    "report_output_path",   # streaming extracts reports from artifacts
})

_actual = set(CodexLaunchSpec.model_fields)
if _actual != _PROJECTED_FIELDS | _DELEGATED_FIELDS:
    missing = _actual - (_PROJECTED_FIELDS | _DELEGATED_FIELDS)
    extra = (_PROJECTED_FIELDS | _DELEGATED_FIELDS) - _actual
    raise ImportError(...)
```

This forces documentation: any field not in `_PROJECTED_FIELDS` must be explicitly marked as delegated or ignored, with a comment. Silent drops are impossible.

## Codex Approval-Mode Event Surface — M9

`codex_ws.py` currently logs a warning when confirm-mode rejects an approval but never emits a `HarnessEvent`. v2 adds:

```python
# In the approval-request handler, when confirm mode rejects:
event = HarnessEvent(
    event_type="warning/approvalRejected",
    payload={
        "reason": "confirm_mode",
        "method": method,
        "message": "confirm-mode requires an interactive channel",
    },
    harness_id=HarnessId.CODEX.value,
)
await self._publish_event(event)
# Then return the JSON-RPC error.
```

Callers subscribing to the event stream see the rejection directly, without inferring it from downstream turn failures.

## OpenCode Projection — Two Functions

### OpenCode Subprocess CLI

```python
# src/meridian/lib/harness/projections/opencode_cli.py
_PROJECTED_FIELDS: frozenset[str] = frozenset({
    "model", "effort", "prompt", "continue_session_id", "continue_fork",
    "permission_resolver", "extra_args", "interactive",
    "agent_name", "skills",
})

def project_opencode_spec_to_cli_args(spec: OpenCodeLaunchSpec) -> list[str]:
    command = ["opencode", "run"]
    if spec.model:
        command.extend(("--model", spec.model))
    if spec.effort:
        command.extend(("--variant", spec.effort))
    if spec.continue_session_id:
        command.extend(("--session", spec.continue_session_id))
        if spec.continue_fork:
            command.append("--fork")
    if spec.agent_name:
        command.extend(("--agent", spec.agent_name))
    # Skills: inlined into the prompt by the runner via RunPromptPolicy.
    # Subprocess does not have a --skills flag.
    command.extend(spec.extra_args)
    command.append("-")  # stdin prompt mode
    return command
```

Permission handling for OpenCode subprocess happens via env overrides (`OPENCODE_PERMISSION`), not CLI flags. The runner's env-build step reads `spec.permission_resolver.config` directly — the projection does not emit permission CLI args. This makes `permission_resolver` a delegated field (same pattern as Codex JSON-RPC):

```python
_PROJECTED_FIELDS: frozenset[str] = frozenset({
    "model", "effort", "agent_name", "continue_session_id",
    "continue_fork", "extra_args", "prompt", "interactive",
})
_DELEGATED_FIELDS: frozenset[str] = frozenset({
    "permission_resolver",  # projected to OPENCODE_PERMISSION env via env.py
    "skills",               # inlined into prompt by RunPromptPolicy
})
```

### OpenCode Streaming — HTTP Session Payload

```python
# src/meridian/lib/harness/projections/opencode_http.py
_PROJECTED_FIELDS: frozenset[str] = frozenset({
    "model", "agent_name", "skills", "continue_session_id",
})
_DELEGATED_FIELDS: frozenset[str] = frozenset({
    "effort",               # no HTTP API support; debug-logged
    "continue_fork",        # no HTTP API support; debug-logged
    "prompt",               # sent via HTTP post-body
    "permission_resolver",  # projected to OPENCODE_PERMISSION env
    "extra_args",           # projected to `opencode serve` launch args
    "interactive",          # streaming is never interactive
})

def project_opencode_spec_to_session_payload(
    spec: OpenCodeLaunchSpec,
) -> dict[str, object]:
    payload: dict[str, object] = {}
    if spec.model:
        payload["model"] = spec.model
        payload["modelID"] = spec.model
    if spec.agent_name:
        payload["agent"] = spec.agent_name
    # M4 resolution: skills are sent via HTTP payload ONLY if the
    # factory preserved them on the spec (skills tuple non-empty means
    # the run_prompt_policy opted out of inlining them into the prompt).
    if spec.skills:
        payload["skills"] = list(spec.skills)
    if spec.continue_session_id:
        payload["session_id"] = spec.continue_session_id
        payload["continue_session_id"] = spec.continue_session_id

    # Debug log for unsupported features
    if spec.effort:
        logger.debug(
            "OpenCode HTTP API does not support effort; field ignored",
            effort=spec.effort,
        )
    if spec.continue_fork:
        logger.debug(
            "OpenCode HTTP API does not support fork; field ignored",
        )
    return payload
```

**M4 — OpenCode skills double-injection.** The factory is responsible for ensuring `spec.skills` is empty whenever `run_prompt_policy().include_skills=True` (which inlines skills into the prompt instead). The projection then unconditionally sends `spec.skills` — if it's empty, nothing is sent. **One authoritative channel.** The tester (E18) exercises both paths.

The decision of which channel is authoritative is made in `OpenCodeAdapter.resolve_launch_spec` after verifying OpenCode HTTP API behavior. v2 defaults to **HTTP payload authoritative, prompt-inlining disabled for streaming**. Rationale: the HTTP `skills` field is more explicit, doesn't bloat the prompt token budget, and is closer to how subprocess forwards per-run skill context. But the verification step (a smoke test against a real OpenCode server confirming the field is honored) must precede the decision lock-in. Deferred to implementation phase — see [edge-cases.md](edge-cases.md) E18.

### OpenCode Streaming — `opencode serve` Launch CLI

```python
def project_opencode_spec_to_serve_command(
    spec: OpenCodeLaunchSpec,
    *,
    port: int,
) -> list[str]:
    command = ["opencode", "serve", "--port", str(port)]
    # Passthrough args — M7 debug log
    if spec.extra_args:
        logger.debug(
            "Forwarding passthrough args to opencode serve",
            extra_args=list(spec.extra_args),
        )
        command.extend(spec.extra_args)
    return command
```

## Projection Completeness Guard — Mechanics

Every projection module runs its import-time check as shown above. The pattern is:

```python
_PROJECTED_FIELDS: frozenset[str] = frozenset({...})
_DELEGATED_FIELDS: frozenset[str] = frozenset({...})  # consumed by sibling module

_actual = set(SpecSubclass.model_fields)
_accounted = _PROJECTED_FIELDS | _DELEGATED_FIELDS
if _actual != _accounted:
    missing = _actual - _accounted
    extra = _accounted - _actual
    raise ImportError(
        f"{SpecSubclass.__name__} projection drift in {__name__}. "
        f"Missing: {missing}. Stale: {extra}."
    )
```

**Why `ImportError` and not `assert`:** `python -O` strips asserts. Every production deployment runs with `-O` potentially. A silent guard on a critical invariant is worse than no guard.

**Why import-time, not first-call:** Import time is the earliest possible failure point. If the projection module is imported at application startup, drift is caught before a single spawn runs.

**Where the projection modules are imported from:** Each is imported unconditionally at the top of its corresponding connection adapter and harness adapter file. Adding a spec field and running `uv run pyright` (or any `uv run meridian` command) surfaces the drift immediately.

**Delegated field comments are mandatory.** Every entry in `_DELEGATED_FIELDS` must be accompanied by a comment explaining which sibling module consumes it. A bare entry with no comment is a code review block.

## Parity Test Shape

Parity tests live at `tests/parity/` and cover:

1. **Claude spec → subprocess args == Claude spec → streaming args** (modulo the base command prefix). Snapshot comparison across the full non-base portion.
2. **Codex spec → subprocess args** contains all permission flags from `permission_resolver.resolve_flags(HarnessId.CODEX)`.
3. **Codex spec → app-server launch command** projects `sandbox` and `approval_policy` from `permission_resolver.config.sandbox` and `.approval`.
4. **Codex spec → JSON-RPC thread request** projects `model` and `effort`.
5. **OpenCode spec → subprocess args + env** covers the full permission surface.
6. **OpenCode spec → HTTP session payload + serve command + env** covers the full permission surface.
7. **Every `CodexLaunchSpec` field** that varies across the eight sandbox/approval combinations produces a distinct wire format.
8. **Every `ClaudeLaunchSpec` field** that varies across the seven permission-resolver types (explicit-tools, deny-list, no-op, etc.) produces a distinct wire format.

Parity tests are parametrized over the full spec-field matrix. When a new field is added, the parametrize decorator or the spec's `model_fields` iteration forces the test to cover it, or the test fails explicitly with "uncovered field."

## Interaction with Other Design Docs

- **Typed harness** ([typed-harness.md](typed-harness.md)) — projection function signatures use the generic-typed spec subclasses.
- **Launch spec** ([launch-spec.md](launch-spec.md)) — defines the fields each projection must handle.
- **Permission pipeline** ([permission-pipeline.md](permission-pipeline.md)) — defines the `config` Protocol property that projections read.
- **Runner shared core** ([runner-shared-core.md](runner-shared-core.md)) — describes how both runners call these projection functions via the shared launch context.
