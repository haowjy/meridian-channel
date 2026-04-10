# Launch Spec

## Purpose

Define the launch-spec hierarchy and the factory contract that maps `SpawnParams` into harness-specific resolved specs. Construction-side accounting catches missing `SpawnParams` mappings; projection-side accounting catches spec-to-wire drift.

This doc complements [typed-harness.md](typed-harness.md), [transport-projections.md](transport-projections.md), and [permission-pipeline.md](permission-pipeline.md).

## Locations

- `src/meridian/lib/harness/launch_types.py` — shared leaf types (`SpawnParams`, `PermissionResolver`, `SpecT`, `ResolvedLaunchSpec`, `PreflightResult`)
- `src/meridian/lib/harness/launch_spec.py` — harness-specific spec subclasses + factory helpers + `SpawnParams` accounting guard

## Hierarchy

### Base — `ResolvedLaunchSpec`

```python
class ResolvedLaunchSpec(BaseModel):
    """Transport-neutral resolved configuration for one harness launch."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    # Identity
    model: str | None = None

    # Execution parameters
    effort: str | None = None
    prompt: str = ""

    # Session continuity
    continue_session_id: str | None = None
    continue_fork: bool = False

    # Permissions
    permission_resolver: PermissionResolver

    # Passthrough args
    extra_args: tuple[str, ...] = ()

    # Interactive mode
    interactive: bool = False

    @model_validator(mode="after")
    def _validate_continue_fork_requires_session(self) -> "ResolvedLaunchSpec":
        if self.continue_fork and not self.continue_session_id:
            raise ValueError("continue_fork=True requires continue_session_id")
        return self
```

The `continue_fork` validator is on the base class so it applies uniformly to Claude, Codex, and OpenCode.

### Claude — `ClaudeLaunchSpec`

```python
class _AgentNameMixin(BaseModel):
    agent_name: str | None = None


class ClaudeLaunchSpec(_AgentNameMixin, ResolvedLaunchSpec):
    """Claude-specific resolved launch spec."""

    agents_payload: str | None = None
    appended_system_prompt: str | None = None
```

### Codex — `CodexLaunchSpec`

**D15 supersedes earlier shape:** sandbox/approval are not stored on `CodexLaunchSpec`. Projection reads `spec.permission_resolver.config.sandbox` and `.config.approval` directly.

```python
class CodexLaunchSpec(ResolvedLaunchSpec):
    """Codex-specific resolved launch spec."""

    # Subprocess-only output path (-o). Streaming ignores this field and
    # extracts reports from artifacts.
    report_output_path: str | None = None
```

### OpenCode — `OpenCodeLaunchSpec`

```python
class OpenCodeLaunchSpec(_AgentNameMixin, ResolvedLaunchSpec):
    """OpenCode-specific resolved launch spec."""

    skills: tuple[str, ...] = ()
```

## Factory Contract

Each concrete adapter implements `resolve_launch_spec(self, run: SpawnParams, perms: PermissionResolver) -> SpecT`.

Rules:

1. Every `SpawnParams` field is either mapped on the spec or explicitly delegated.
2. `perms` is non-optional; callers with no permission context must opt in explicitly via `UnsafeNoOpPermissionResolver`.
3. Normalization happens once in factory helpers; projections do wire mapping only.
4. Adapter return type is concrete (`ClaudeLaunchSpec`, `CodexLaunchSpec`, `OpenCodeLaunchSpec`), not base.

### Example: Codex Factory (post-D15)

```python
class CodexAdapter(HarnessAdapter[CodexLaunchSpec]):
    def resolve_launch_spec(
        self,
        run: SpawnParams,
        perms: PermissionResolver,
    ) -> CodexLaunchSpec:
        return CodexLaunchSpec(
            model=_normalize_model(run.model),
            effort=run.effort,
            prompt=run.prompt,
            continue_session_id=_normalize_session_id(run.continue_harness_session_id),
            continue_fork=run.continue_fork,
            permission_resolver=perms,
            extra_args=run.extra_args,
            interactive=run.interactive,
            report_output_path=run.report_output_path,
        )
```

No `_map_sandbox_mode` / `_map_approval_mode` helper is used at construction time. Mapping lives in the Codex projection module.

## Completeness Guard — Construction Side

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

# No delegated SpawnParams fields in v2.
_SPEC_DELEGATED_FIELDS: frozenset[str] = frozenset()

_actual_fields = set(SpawnParams.model_fields)
_accounted_fields = _SPEC_HANDLED_FIELDS | _SPEC_DELEGATED_FIELDS
if _actual_fields != _accounted_fields:
    missing = _actual_fields - _accounted_fields
    extra = _accounted_fields - _actual_fields
    raise ImportError(
        "SpawnParams accounting drift. "
        f"Missing: {missing}. Stale: {extra}."
    )
```

This guard enforces that every `SpawnParams` field has a home somewhere in the system. It does not enforce per-adapter completeness — an adapter that ignores a field will not trip this guard. Per-adapter completeness is enforced at the projection layer via `_PROJECTED_FIELDS` / `_ACCOUNTED_FIELDS`.

## Interaction with Other Docs

- [typed-harness.md](typed-harness.md): generic adapter/connection contracts and dispatch guard.
- [transport-projections.md](transport-projections.md): wire mapping + transport-wide completeness checks.
- [permission-pipeline.md](permission-pipeline.md): non-optional resolver and strict REST defaults.
