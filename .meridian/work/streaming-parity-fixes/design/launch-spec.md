# Launch Spec

## Purpose

Define the `ResolvedLaunchSpec` hierarchy, field ownership per harness, the factory contract that produces it, and the import-time completeness guard that catches a missed `SpawnParams` field. The spec is the single policy layer — any normalization, field mapping, or harness-specific semantic decision lives in the factory, not in a transport projection or a runner.

This doc complements [typed-harness.md](typed-harness.md) (type contract) and [transport-projections.md](transport-projections.md) (wire-format mapping).

## Location

`src/meridian/lib/harness/launch_spec.py` — the module already exists in v1. v2 re-shapes field ownership, deletes the permission getattr fallback, and replaces the `assert` with an `ImportError`.

## Hierarchy

### Base — `ResolvedLaunchSpec`

Carries only fields that are semantically shared across every harness. The v1 spec placed `report_output_path` here even though only Codex uses it (M5). v2 moves Codex-only fields to `CodexLaunchSpec`.

```python
class ResolvedLaunchSpec(BaseModel):
    """Transport-neutral resolved configuration for one harness launch."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    # Identity
    model: str | None = None

    # Execution parameters — already normalized to harness-native value.
    effort: str | None = None
    prompt: str = ""

    # Session continuity
    continue_session_id: str | None = None
    continue_fork: bool = False

    # Permissions — semantic, not CLI-shaped.
    # resolver carries config; projections read resolver.config
    # or call resolver.resolve_flags(harness_id).
    permission_resolver: PermissionResolver

    # Passthrough args (transport-specific; see M3/H2 handling in
    # transport-projections.md for dedupe/ordering semantics).
    extra_args: tuple[str, ...] = ()

    # Interactive mode — always False for streaming connections.
    interactive: bool = False
```

Note: `permission_resolver` is **non-optional** on the spec (see [permission-pipeline.md](permission-pipeline.md) for the rationale). The `permission_config` field is removed — projections access it via `permission_resolver.config` since the resolver now exposes `config` as a required Protocol property. This eliminates the v1 dual-field redundancy (both `permission_config` and `permission_resolver` were stored) and the `resolve_permission_config(perms)` getattr chain.

The v1 `report_output_path` field moves off the base class. The v1 `mcp_config` field is already unused — delete it from the base. If MCP wiring lands later, it adds a per-harness field.

### Claude — `ClaudeLaunchSpec`

```python
class ClaudeLaunchSpec(ResolvedLaunchSpec):
    """Claude-specific resolved launch spec."""

    # Agent profile via --agent
    agent_name: str | None = None

    # Native agent payload via --agents
    agents_payload: str | None = None

    # Skill injection via --append-system-prompt
    appended_system_prompt: str | None = None
```

Claude uses the base's `continue_session_id` + `continue_fork` directly (maps to `--resume` + `--fork-session`).

### Codex — `CodexLaunchSpec`

```python
class CodexLaunchSpec(ResolvedLaunchSpec):
    """Codex-specific resolved launch spec."""

    # Sandbox mode for --sandbox flag / -c sandbox_mode override.
    # None means "use Codex default". Non-None values: "read-only",
    # "workspace-write", "danger-full-access".
    sandbox_mode: str | None = None

    # Approval mode. Projections translate semantically:
    # "default" → harness default
    # "auto" → accept all
    # "yolo" → accept all (surfaced as separate mode for
    #          observability/audit trail)
    # "confirm" → streaming: reject with warning event; subprocess:
    #             --ask-for-approval handled by permission resolver.
    approval_mode: Literal["default", "auto", "yolo", "confirm"] = "default"

    # Report output path — subprocess projects to -o <path>.
    # Streaming logs a debug warning (Codex streaming extracts reports
    # from artifacts instead).
    report_output_path: str | None = None
```

M5 resolved: `report_output_path` is no longer on the base.

### OpenCode — `OpenCodeLaunchSpec`

```python
class OpenCodeLaunchSpec(ResolvedLaunchSpec):
    """OpenCode-specific resolved launch spec."""

    # Agent name for session creation payload.
    agent_name: str | None = None

    # Skills for the session creation payload.
    # The policy (prompt inlining vs HTTP field) is decided at
    # spec-construction time by reading run_prompt_policy.include_skills
    # and adjusted in the factory. See transport-projections.md for
    # M4 resolution.
    skills: tuple[str, ...] = ()
```

### Why not a universal flat struct?

Three reasons the per-harness subclasses stay:

1. **Type-guided projection.** The projection functions receive a concrete subclass. `project_claude_spec_to_cli_args(spec: ClaudeLaunchSpec)` has static access to `spec.appended_system_prompt` without an isinstance check.
2. **Field-existence enforcement.** A Claude-only field on a flat struct would have to be `Optional`, and projections would need to check for None at runtime. Per-harness subclass keeps the field absent entirely from specs for other harnesses.
3. **Completeness guard granularity.** The projection-side `_PROJECTED_FIELDS` check is per-subclass. A flat struct would make this check meaningless because every field would show up in every harness's projection.

### Shared field: `agent_name`

v1 had `agent_name` on both `ClaudeLaunchSpec` and `OpenCodeLaunchSpec` (L3). Both use it identically — carry the agent profile name for the respective CLI/HTTP target. v2 keeps both subclass definitions but sources the field from a shared mixin to prevent drift:

```python
class _AgentNameMixin(BaseModel):
    agent_name: str | None = None

class ClaudeLaunchSpec(_AgentNameMixin, ResolvedLaunchSpec):
    agents_payload: str | None = None
    appended_system_prompt: str | None = None

class OpenCodeLaunchSpec(_AgentNameMixin, ResolvedLaunchSpec):
    skills: tuple[str, ...] = ()
```

Alternative: promote `agent_name` to the base. This is tempting but wrong — Codex doesn't use it and promoting it signals "every harness has an agent_name" when Codex doesn't. The mixin preserves the semantics.

## Factory Contract

Each adapter implements `resolve_launch_spec` as its required abstract method. The factory is the single place where `SpawnParams` fields become spec fields. Normalization (effort, model prefix stripping, session id trimming, adhoc payload whitespace) happens here, not in projections.

### Factory Rules

1. **Every `SpawnParams` field is either consumed or explicitly delegated.** The `_SPEC_HANDLED_FIELDS` check enforces this at import time.
2. **No runtime None-casts.** `perms: PermissionResolver` — never `None`, never `Optional`.
3. **No silent defaults.** If a field has a meaningful default, make it explicit in the factory body with a comment.
4. **Single normalization site.** Double-normalization (L10: `claude.py:266-269` normalizes effort twice) is a structural error. Remove the second pass.
5. **Adapter factories bind their subclass return type.** `def resolve_launch_spec(self, run, perms) -> ClaudeLaunchSpec:` — not `ResolvedLaunchSpec`.

### Example: Claude Factory

```python
class ClaudeAdapter(HarnessAdapter[ClaudeLaunchSpec]):
    def resolve_launch_spec(
        self,
        run: SpawnParams,
        perms: PermissionResolver,
    ) -> ClaudeLaunchSpec:
        return ClaudeLaunchSpec(
            # Base fields
            model=_normalize_model(run.model),
            effort=_normalize_claude_effort(run.effort),
            prompt=run.prompt,
            continue_session_id=_normalize_session_id(run.continue_harness_session_id),
            continue_fork=run.continue_fork,
            permission_resolver=perms,
            extra_args=run.extra_args,
            interactive=run.interactive,
            # Claude-specific
            agent_name=run.agent,
            agents_payload=_normalize_adhoc_payload(run.adhoc_agent_payload),
            appended_system_prompt=run.appended_system_prompt,
        )
```

`_normalize_claude_effort` lives in `claude.py` and converts `"xhigh"` → `"max"` exactly once. The projection function emits it verbatim.

### Example: Codex Factory

```python
class CodexAdapter(HarnessAdapter[CodexLaunchSpec]):
    def resolve_launch_spec(
        self,
        run: SpawnParams,
        perms: PermissionResolver,
    ) -> CodexLaunchSpec:
        approval_mode = _map_approval_mode(perms.config.approval)
        sandbox_mode = _map_sandbox_mode(perms.config.sandbox)
        return CodexLaunchSpec(
            model=_normalize_model(run.model),
            effort=run.effort,  # Codex effort is already the raw value
            prompt=run.prompt,
            continue_session_id=_normalize_session_id(run.continue_harness_session_id),
            continue_fork=run.continue_fork,
            permission_resolver=perms,
            extra_args=run.extra_args,
            interactive=run.interactive,
            # Codex-specific
            sandbox_mode=sandbox_mode,
            approval_mode=approval_mode,
            report_output_path=run.report_output_path,
        )
```

The factory reads `perms.config` — which is guaranteed non-None by the Protocol property (see [permission-pipeline.md](permission-pipeline.md)) — to populate `sandbox_mode` / `approval_mode`. This is Codex-specific semantic knowledge: Codex streaming consults these fields in its projection, not raw CLI permission flags.

### Example: OpenCode Factory

```python
class OpenCodeAdapter(HarnessAdapter[OpenCodeLaunchSpec]):
    def resolve_launch_spec(
        self,
        run: SpawnParams,
        perms: PermissionResolver,
    ) -> OpenCodeLaunchSpec:
        return OpenCodeLaunchSpec(
            model=_normalize_opencode_model(run.model),  # strips opencode- prefix
            effort=run.effort,  # no native effort support; projected to debug log
            prompt=run.prompt,
            continue_session_id=_normalize_session_id(run.continue_harness_session_id),
            continue_fork=run.continue_fork,
            permission_resolver=perms,
            extra_args=run.extra_args,
            interactive=run.interactive,
            # OpenCode-specific
            agent_name=run.agent,
            skills=_resolve_opencode_skills(run.skills),
        )
```

Skill resolution flow (M4): the factory looks at the adapter's `run_prompt_policy().include_skills`. If the policy is `include_skills=True`, skills are inlined into the prompt by the runner via `RunPromptPolicy` — the factory then sets `skills=()` on the spec (empty tuple) so the HTTP projection cannot re-send them. If the policy is `include_skills=False`, skills stay on the spec and the HTTP projection sends them via the `skills` payload field. **Exactly one authoritative channel.** The tester exercises both paths.

## Completeness Guard — Construction Side

The v1 `_SPEC_HANDLED_FIELDS` check uses `assert`, which strips under `python -O`. v2 replaces it with a real `ImportError`:

```python
# src/meridian/lib/harness/launch_spec.py
_SPEC_HANDLED_FIELDS: frozenset[str] = frozenset({
    "prompt",
    "model",
    "effort",
    "skills",
    "agent",
    "adhoc_agent_payload",
    "extra_args",
    "repo_root",
    "interactive",
    "continue_harness_session_id",
    "continue_fork",
    "appended_system_prompt",
    "report_output_path",
})

# Fields that exist on SpawnParams but are NOT forwarded to the spec
# because another subsystem owns them. Each entry has a comment
# explaining the delegation.
_SPEC_DELEGATED_FIELDS: frozenset[str] = frozenset({
    "mcp_tools",  # handled by env.py in build_harness_child_env
})

_actual_fields: set[str] = set(SpawnParams.model_fields)
_accounted_fields: set[str] = _SPEC_HANDLED_FIELDS | _SPEC_DELEGATED_FIELDS

if _actual_fields != _accounted_fields:
    missing = _actual_fields - _accounted_fields
    extra = _accounted_fields - _actual_fields
    raise ImportError(
        "SpawnParams field set drifted from launch spec accounting. "
        f"Missing from _SPEC_HANDLED_FIELDS / _SPEC_DELEGATED_FIELDS: {missing}. "
        f"Stale entries: {extra}. "
        "Update src/meridian/lib/harness/launch_spec.py and every "
        "adapter.resolve_launch_spec implementation."
    )
```

Three improvements over v1:

1. **`ImportError`, not `assert`.** Survives `python -O` and anything that strips asserts.
2. **`_SPEC_DELEGATED_FIELDS` is explicit.** L2 is fixed: `mcp_tools` has a clear home in the delegated set, not the handled set where it was lying.
3. **Error message is actionable.** It names the drift set and points at the files to update.

This guard only covers `SpawnParams → spec`. The symmetric `spec → wire` guard lives in [transport-projections.md](transport-projections.md).

## Immutability and Factory Location

Every spec class uses `model_config = ConfigDict(frozen=True)`. Mutating a spec after construction is a type error. Transport projections produce new data structures (CLI arg lists, JSON-RPC param dicts, HTTP payload dicts) rather than modifying the spec.

The factory method is the only place that constructs a spec subclass. No other module in the codebase should call `ClaudeLaunchSpec(...)` directly — parity tests are the only exception, and they use a helper builder in the test fixtures.

Grep discipline: any non-test module outside of `claude.py`/`codex.py`/`opencode.py` that constructs a spec subclass is a code smell and should be reviewed.

## Session Continuity Edge Cases

- `continue_session_id` is trimmed to `None` if empty/whitespace. Both runners and both projections must behave identically.
- `continue_fork=True` with `continue_session_id=None` is a caller error. v1 silently ignored it. v2 raises `ValueError` in the factory — surfacing the misconfiguration. Tested by scenario E20.
- `continue_session_id` with leading/trailing whitespace: trimmed in the factory. Projections see the clean value.

## Model Normalization

`_normalize_model(run.model)` lives in `launch_spec.py` as a shared helper since Claude/Codex both strip whitespace and fall back to `None`. OpenCode adds a prefix-strip step; its helper wraps the shared one.

```python
def _normalize_model(model: ModelId | None) -> str | None:
    if model is None:
        return None
    normalized = str(model).strip()
    return normalized or None

def _normalize_opencode_model(model: ModelId | None) -> str | None:
    base = _normalize_model(model)
    if base and base.startswith("opencode-"):
        return base[len("opencode-"):]
    return base
```

This is the single normalization site. The v1 double-normalization in `claude.py:266-269` (effort normalized in the factory, then again in `build_command`) is deleted — `build_command` projects the already-normalized value.

## Interaction with Other Design Docs

- **Typed harness** ([typed-harness.md](typed-harness.md)) — specifies the `HarnessAdapter[SpecT]` type contract. This doc fills in the SpecT hierarchy and factory body.
- **Transport projections** ([transport-projections.md](transport-projections.md)) — specifies the wire-format mapping. Projections consume the spec; this doc defines what fields exist.
- **Permission pipeline** ([permission-pipeline.md](permission-pipeline.md)) — specifies that `PermissionResolver` is non-optional and `config` is a required property. This doc's factory signature depends on that contract.
