# Launch Spec

## Purpose

Define the launch-spec hierarchy and the factory contract that maps `SpawnParams` into harness-specific resolved specs. Construction-side accounting catches missing `SpawnParams` mappings; projection-side accounting catches spec-to-wire drift.

This doc complements [typed-harness.md](typed-harness.md), [transport-projections.md](transport-projections.md), and [permission-pipeline.md](permission-pipeline.md).

Revision round 3 changes:

- `mcp_tools` is restored as a first-class forwarded field (D4, reversing round 2 D23). Auto-packaging through mars is out of scope for v2, but manual configuration flows through today.
- Every adapter declares a `handled_fields: frozenset[str]` property (K9). The union across registered adapters must equal `SpawnParams.model_fields` at import time.

## Locations

- `src/meridian/lib/launch/launch_types.py` — shared leaf types (`PermissionResolver`, `SpecT`, `ResolvedLaunchSpec`, `PreflightResult`)
- `src/meridian/lib/launch/spawn_params.py` — `SpawnParams` itself
- `src/meridian/lib/harness/launch_spec.py` — harness-specific spec subclasses + factory helpers + cross-adapter accounting guards

## Hierarchy

### Base — `ResolvedLaunchSpec`

Base class `ResolvedLaunchSpec` lives in `launch_types.py` — see [typed-harness.md](typed-harness.md#module-launchlaunch_typespy). This includes:

- the base `continue_fork` validator
- `mcp_tools: tuple[str, ...] = ()` so every harness can forward MCP configuration
- `extra_args: tuple[str, ...] = ()` forwarded verbatim (no stripping)
- `model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)` — construction-time freeze (K7)

### Claude — `ClaudeLaunchSpec`

```python
class ClaudeLaunchSpec(ResolvedLaunchSpec):
    """Claude-specific resolved launch spec."""

    agent_name: str | None = None
    agents_payload: str | None = None
    appended_system_prompt: str | None = None
```

### Codex — `CodexLaunchSpec`

**D15 still applies:** sandbox/approval are not stored on `CodexLaunchSpec`. Projection reads `spec.permission_resolver.config.sandbox` and `.config.approval` directly.

```python
class CodexLaunchSpec(ResolvedLaunchSpec):
    """Codex-specific resolved launch spec."""

    # Subprocess-only output path (-o). Streaming ignores this field and
    # extracts reports from artifacts.
    report_output_path: str | None = None
```

### OpenCode — `OpenCodeLaunchSpec`

```python
class OpenCodeLaunchSpec(ResolvedLaunchSpec):
    """OpenCode-specific resolved launch spec."""

    agent_name: str | None = None
    skills: tuple[str, ...] = ()
```

## Factory Contract

Each concrete adapter implements `resolve_launch_spec(self, run: SpawnParams, perms: PermissionResolver) -> SpecT`.

Rules:

1. Every `SpawnParams` field is either mapped on the spec or explicitly delegated.
2. `perms` is non-optional; callers with no permission context must opt in explicitly via `UnsafeNoOpPermissionResolver`.
3. Normalization happens once in factory helpers; projections do wire mapping only.
4. Adapter return type is concrete (`ClaudeLaunchSpec`, `CodexLaunchSpec`, `OpenCodeLaunchSpec`), not base.
5. Every adapter exposes `handled_fields: frozenset[str]` — the set of `SpawnParams` field names it consumes. Global accounting (§"Completeness Guard — Construction Side") asserts `∪ adapter.handled_fields == SpawnParams.model_fields`.
6. `extra_args` is never filtered or rewritten by the factory or the projection. It flows through verbatim.

### Example: Codex Factory (post-D15 + revision round 3)

```python
class CodexAdapter(HarnessAdapter[CodexLaunchSpec]):
    @property
    def id(self) -> HarnessId:
        return HarnessId.CODEX

    @property
    def handled_fields(self) -> frozenset[str]:
        return _CODEX_HANDLED_FIELDS

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
            mcp_tools=run.mcp_tools,
            report_output_path=run.report_output_path,
        )


_CODEX_HANDLED_FIELDS: frozenset[str] = frozenset({
    "model",
    "effort",
    "prompt",
    "continue_harness_session_id",
    "continue_fork",
    "extra_args",
    "interactive",
    "mcp_tools",
    "report_output_path",
    # Codex consumes these indirectly via preflight / env, not spec fields:
    "repo_root",
    # Codex ignores these explicitly (captured under handled because the
    # adapter makes the decision, rather than letting the field vanish):
    "skills",
    "agent",
    "adhoc_agent_payload",
    "appended_system_prompt",
})
```

No `_map_sandbox_mode` / `_map_approval_mode` helper is used at construction time. Mapping lives in the Codex projection module.

### Claude Factory `handled_fields`

```python
_CLAUDE_HANDLED_FIELDS: frozenset[str] = frozenset({
    "prompt",
    "model",
    "effort",
    "skills",        # consumed via agents_payload assembly in preflight
    "agent",
    "adhoc_agent_payload",
    "extra_args",
    "repo_root",
    "interactive",
    "continue_harness_session_id",
    "continue_fork",
    "appended_system_prompt",
    "mcp_tools",
    # Claude does not use report_output_path; adapter declares it handled
    # with an explicit ignore rule rather than letting it vanish:
    "report_output_path",
})
```

### OpenCode Factory `handled_fields`

```python
_OPENCODE_HANDLED_FIELDS: frozenset[str] = frozenset({
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
    "mcp_tools",
    # ignored but explicitly declared:
    "appended_system_prompt",
    "report_output_path",
})
```

## Completeness Guards

### Global Guard (union across adapters)

```python
# src/meridian/lib/harness/launch_spec.py
from meridian.lib.launch.spawn_params import SpawnParams
from meridian.lib.harness.bundle import _REGISTRY

def _enforce_spawn_params_accounting() -> None:
    expected = set(SpawnParams.model_fields)
    union: set[str] = set()
    for bundle in _REGISTRY.values():
        union |= set(bundle.adapter.handled_fields)
    missing = expected - union
    stale = union - expected
    if missing or stale:
        raise ImportError(
            "SpawnParams cross-adapter accounting drift. "
            f"Missing: {sorted(missing)}. Stale: {sorted(stale)}."
        )
```

This check runs at the tail of `harness/__init__.py` eager import sequence, after every bundle is registered. It is strictly about meridian-internal drift: if a developer adds a new `SpawnParams` field without claiming it on any adapter, the package fails to import (S006, S044).

### Legacy global handled set (retained as the field name enumeration)

`_SPEC_HANDLED_FIELDS` is retained as the *authoritative name set* for `SpawnParams` fields that any adapter might handle — it is the pre-registration snapshot used to cross-reference test fixtures and to seed adapter defaults during migration.

```python
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
    "mcp_tools",
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

This guard enforces that every `SpawnParams` field has a home somewhere in the system. The *per-adapter* guard (above) enforces that every field is claimed by at least one adapter, and it runs after bundle registration. Per-adapter completeness at the projection layer is still enforced via `_PROJECTED_FIELDS` / `_ACCOUNTED_FIELDS` in each projection module.

K9 closes the gap in the earlier design where `_SPEC_HANDLED_FIELDS` could be satisfied globally while one adapter silently noops a field.

## Interaction with Other Docs

- [typed-harness.md](typed-harness.md): generic adapter/connection/extractor contracts, dispatch guard, bundle registration.
- [transport-projections.md](transport-projections.md): wire mapping + transport-wide completeness checks + `mcp_tools` projection.
- [permission-pipeline.md](permission-pipeline.md): non-optional resolver, immutable config, strict REST defaults.
