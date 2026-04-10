# Permission Pipeline

## Purpose

Eliminate `cast("PermissionResolver", None)` and the `resolve_permission_config(perms)` getattr fallback chain by making the resolver non-optional end-to-end and promoting `config` to a required Protocol property. This doc resolves H3 (two `cast` sites), L6 (cast obscures intent), and the related `PermissionResolver` Protocol gap noted in the v1 decision log D17 triage.

## Root Cause

Under v1, two entry points construct a `ResolvedLaunchSpec` without having a `PermissionResolver` in hand:

1. `src/meridian/lib/launch/streaming_runner.py:457` — `run_streaming_spawn()` is a public API called from CLI entrypoints that don't necessarily plumb through a plan with a resolver.
2. `src/meridian/lib/app/server.py:203` — the REST server's POST handler constructs a spec from HTTP body inputs, with no permission context threaded in.

Both sites cast `None` to `PermissionResolver`, which bypasses the type checker. Downstream, `resolve_permission_config(perms)` walks a getattr chain (`perms.config`, `perms.fallback_config`, `perms.allowlist.fallback_config`, `perms.denylist.fallback_config`) and falls through to an empty `PermissionConfig()`. The result:

- Claude streaming emits zero permission flags (no `--allowedTools`, no `--add-dir`, no denies).
- Codex streaming collapses to accept-all regardless of configuration.
- OpenCode env overrides become empty, so `OPENCODE_PERMISSION` is missing.

This is not a bug in a single file. It is a failure of the type system at the adapter boundary — the signature lied, the type checker accepted the lie, and the fallback chain converted the lie into silent default behavior.

## Target Shape

### 1. `PermissionResolver.config` Becomes a Required Protocol Property

```python
# src/meridian/lib/harness/adapter.py
from typing import Protocol, runtime_checkable
from meridian.lib.safety.permissions import PermissionConfig
from meridian.lib.core.types import HarnessId

@runtime_checkable
class PermissionResolver(Protocol):
    """Resolves PermissionConfig into harness-specific effects."""

    @property
    def config(self) -> PermissionConfig:
        """Return the underlying PermissionConfig.

        Every resolver must expose its config. Projections read this
        instead of calling getattr chains. This is the single
        authoritative source for sandbox/approval mode and the
        allow/deny surface.
        """
        ...

    def resolve_flags(self, harness: HarnessId) -> tuple[str, ...]:
        """Return the CLI flags needed to enforce this config on the
        named harness. Returns empty tuple for harnesses that enforce
        permissions out-of-band (e.g., OpenCode via env)."""
        ...
```

The Protocol gains a `config` property. Every existing resolver implementation in `src/meridian/lib/safety/permissions.py` gains the property — they all already have access to a `PermissionConfig`, so this is a signature tightening, not new behavior.

```python
# src/meridian/lib/safety/permissions.py
class TieredPermissionResolver(BaseModel):
    config: PermissionConfig  # already exists as a field — just promote to the Protocol

    def resolve_flags(self, harness: HarnessId) -> tuple[str, ...]: ...
```

```python
class ExplicitToolsResolver(BaseModel):
    allowed_tools: tuple[str, ...]
    _config: PermissionConfig  # private

    @property
    def config(self) -> PermissionConfig:
        return self._config

    def resolve_flags(self, harness: HarnessId) -> tuple[str, ...]: ...
```

```python
class NoOpPermissionResolver(BaseModel):
    """Resolver that intentionally enforces no permissions.

    Callers using this resolver explicitly opt out of permission
    enforcement. A warning is logged at construction time so misuse is
    visible in spawn logs. Use only at entry points that truly have no
    permission context (e.g., a read-only REST health endpoint).
    """

    def __init__(self, **data: object) -> None:
        super().__init__(**data)
        logger.warning(
            "NoOpPermissionResolver instantiated — spawn will run with "
            "no enforced permission surface. This is a caller opt-in; "
            "verify the call site intends this behavior."
        )

    @property
    def config(self) -> PermissionConfig:
        return PermissionConfig()

    def resolve_flags(self, harness: HarnessId) -> tuple[str, ...]:
        return ()
```

### 2. Delete `resolve_permission_config(perms)`

The module-level helper in `launch_spec.py` goes away:

```python
# DELETE THIS
def resolve_permission_config(perms: PermissionResolver) -> PermissionConfig:
    config = getattr(perms, "config", None)
    ...
    return PermissionConfig()
```

Projections and factories read `perms.config` directly. No fallback, no ambiguity, no silent default. The Protocol property guarantees the field exists.

### 3. Factory Signatures Are Honest

Every adapter `resolve_launch_spec` signature is:

```python
def resolve_launch_spec(
    self,
    run: SpawnParams,
    perms: PermissionResolver,  # non-optional, non-None
) -> SpecT:
```

No `Optional`, no default value, no `cast`. Callers must pass a real resolver.

### 4. Entry-Point Fix: `run_streaming_spawn`

`run_streaming_spawn` currently takes a `ConnectionConfig` and `SpawnParams`. Under v2 it takes a `PermissionResolver` as well:

```python
async def run_streaming_spawn(
    *,
    config: ConnectionConfig,
    params: SpawnParams,
    perms: PermissionResolver,  # NEW: non-optional
    state_root: Path,
    repo_root: Path,
    spawn_id: SpawnId,
    stream_to_terminal: bool = False,
) -> DrainOutcome:
    adapter = get_harness_bundle(config.harness_id).adapter
    run_spec = adapter.resolve_launch_spec(params, perms)
    ...
```

Callers of `run_streaming_spawn` must provide a resolver. There are two classes of caller:

- **Plan-aware callers** — already have a `plan.execution.permission_resolver`. They pass it in directly.
- **Plan-agnostic callers** (tests, lightweight CLI entry points) — construct a `NoOpPermissionResolver()` or (preferred) build a `TieredPermissionResolver` from project config via `build_permission_resolver()`.

The REST server is the second class. It constructs a resolver from request context (or from server defaults) before calling `adapter.resolve_launch_spec`. No cast, no None.

### 5. Entry-Point Fix: `server.py:203`

```python
# src/meridian/lib/app/server.py
# BEFORE:
spec = adapter.resolve_launch_spec(
    params, cast("PermissionResolver", None)
)

# AFTER:
permission_resolver = self._resolve_request_permissions(body)
spec = adapter.resolve_launch_spec(params, permission_resolver)
```

Where `_resolve_request_permissions(body)` either:
- Constructs a `TieredPermissionResolver` from the request body if it carries permission config, or
- Constructs `NoOpPermissionResolver()` with the warning log if the request is permission-free and the server is configured to allow that, or
- Raises `HTTPException(400)` if the server requires explicit permission context and none is provided.

The server's policy on permission requirements is a configuration choice, documented in the REST server docs. v2 defaults to `NoOpPermissionResolver` for backward compatibility but logs a loud warning.

### 6. Delete the `cast("PermissionResolver", None)` Sites

With the above in place, the two `cast` sites vanish. Pyright enforces that a real resolver is always present at the adapter boundary.

## PermissionConfig Is The Single Source of Truth

Both subprocess and streaming paths read permission state from `spec.permission_resolver.config`. No code path reads a duplicate field elsewhere.

Before: `CodexLaunchSpec.sandbox_mode` and `.approval_mode` duplicate what's in `permission_resolver.config.sandbox` and `.approval`. Two fields means two sources of truth that can drift.

After: `CodexLaunchSpec` carries neither `sandbox_mode` nor `approval_mode`. Projections read them from `spec.permission_resolver.config`. See [launch-spec.md](launch-spec.md) and [transport-projections.md](transport-projections.md).

## Test Coverage

Unit tests under `tests/unit/lib/safety/` assert that every resolver implementation exposes `config` and that the property always returns a valid `PermissionConfig` (never `None`, never raises). Fixture-driven tests exercise each concrete resolver against the Protocol to catch drift.

Smoke tests cover:
- E13: REST server accepts a spawn request with no permission block. A `NoOpPermissionResolver` is constructed, a warning is logged, spawn runs.
- E14: `run_streaming_spawn` accepts a caller-supplied `TieredPermissionResolver`. The resolver's config reaches `project_codex_spec_to_appserver_command` and the resulting `-c sandbox_mode` / `-c approval_policy` overrides appear on the wire.
- E3: a test that attempts to pass `None` as `perms` must fail pyright. The test file uses `# type: ignore[arg-type]` with a comment explaining the expected failure; CI pyright step would reject the file without the ignore.

## Interaction with Other Design Docs

- **Typed harness** ([typed-harness.md](typed-harness.md)) — `HarnessAdapter[SpecT]` Protocol specifies the factory signature that depends on `PermissionResolver` being non-optional.
- **Launch spec** ([launch-spec.md](launch-spec.md)) — removes `permission_config` from the base spec because projections read it from the resolver.
- **Transport projections** ([transport-projections.md](transport-projections.md)) — every projection reads `spec.permission_resolver.config` directly.
- **Runner shared core** ([runner-shared-core.md](runner-shared-core.md)) — the shared launch-context assembly step is the single place that forwards `plan.execution.permission_resolver` into the adapter factory.
