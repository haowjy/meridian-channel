# Typed Harness Contract

## Purpose

Eliminate isinstance branching and silent base-class fallbacks by binding each harness adapter and its connection adapter to their specific `ResolvedLaunchSpec` subclass through `Generic[SpecT]`. The type checker enforces that a `ClaudeConnection` cannot be called with a `CodexLaunchSpec`, that a `ResolvedLaunchSpec` base instance cannot reach `ClaudeConnection.start`, and that a spec factory cannot be omitted.

This doc specifies the type shape. The subsequent docs ([launch-spec.md](launch-spec.md), [transport-projections.md](transport-projections.md)) specify the field-level contracts.

## The TypeVar

```python
# src/meridian/lib/harness/launch_spec.py
from typing import TypeVar

SpecT = TypeVar("SpecT", bound="ResolvedLaunchSpec")
SpecT_co = TypeVar("SpecT_co", bound="ResolvedLaunchSpec", covariant=True)
```

`SpecT` binds to `ResolvedLaunchSpec` and is used invariantly where the spec is both produced and consumed (e.g., adapter methods that take `SpecT` as input). `SpecT_co` is covariant and is used where the spec is only produced (e.g., factory return type in a Protocol). The distinction matters only if we need to accept `HarnessAdapter[ClaudeLaunchSpec]` where `HarnessAdapter[ResolvedLaunchSpec]` is expected — which we don't, so invariant `SpecT` is sufficient in practice.

## Adapter Contract

`HarnessAdapter` becomes a generic Protocol that binds to the spec type its factory produces. There is **no base-class fallback implementation** of `resolve_launch_spec`. Any concrete adapter that omits it fails at type-check time (the Protocol method isn't satisfied) and at instantiation time (abstract method not implemented).

```python
# src/meridian/lib/harness/adapter.py
from typing import Generic, Protocol, runtime_checkable

@runtime_checkable
class HarnessAdapter(Protocol, Generic[SpecT]):
    """Transport-agnostic contract every harness adapter satisfies."""

    @property
    def id(self) -> HarnessId: ...

    @property
    def capabilities(self) -> HarnessCapabilities: ...

    def resolve_launch_spec(
        self,
        run: SpawnParams,
        perms: PermissionResolver,
    ) -> SpecT:
        """Produce a fully-resolved launch spec for this harness.

        This method is the single policy layer. Every SpawnParams field
        that affects harness launch must be mapped here. The
        _SPEC_HANDLED_FIELDS import-time guard in launch_spec.py verifies
        that every SpawnParams field is accounted for.

        ``perms`` is non-optional. Callers that have no permission
        context must construct a ``NoOpPermissionResolver`` explicitly
        and accept the logged warning.
        """
        ...

    def build_command(
        self,
        run: SpawnParams,
        perms: PermissionResolver,
    ) -> list[str]:
        """Build the subprocess CLI command for this harness.

        Thin wrapper over ``resolve_launch_spec`` + the shared
        projection function for this harness.
        """
        ...

    # ... other adapter methods (run_prompt_policy, mcp_config, etc.)
```

Concrete adapters bind their spec subclass:

```python
# src/meridian/lib/harness/claude.py
class ClaudeAdapter(HarnessAdapter[ClaudeLaunchSpec]):
    def resolve_launch_spec(
        self,
        run: SpawnParams,
        perms: PermissionResolver,
    ) -> ClaudeLaunchSpec:
        ...

    def build_command(
        self,
        run: SpawnParams,
        perms: PermissionResolver,
    ) -> list[str]:
        spec = self.resolve_launch_spec(run, perms)
        return project_claude_spec_to_command(
            spec,
            base_command=list(self.SUBPROCESS_BASE_COMMAND),
        )
```

`BaseSubprocessHarness.resolve_launch_spec` **is deleted**. The base class still carries no-op defaults for truly optional methods (`mcp_config`, `env_overrides`, `fork_session`, `seed_session`, `filter_launch_content`, `detect_primary_session_id`, `owns_untracked_session`, `blocked_child_env_vars`) but `resolve_launch_spec` is not one of them — it's the primary contract.

## Connection Contract

`HarnessConnection` becomes a `Generic[SpecT]` abstract base class (not a runtime Protocol) so that:
- Subclasses can be detected at class definition time via abstract method enforcement.
- The spec parameter on `start()` is typed with the concrete subclass, so isinstance branching is impossible.
- Subclasses that forget a method fail at instantiation, not at first call.

```python
# src/meridian/lib/harness/connections/base.py
from abc import ABC, abstractmethod
from typing import Generic

class HarnessConnection(Generic[SpecT], ABC):
    """Abstract base for full-duplex harness connections.

    Subclasses bind SpecT to their specific launch spec subclass,
    e.g. ``ClaudeConnection(HarnessConnection[ClaudeLaunchSpec])``.
    """

    @property
    @abstractmethod
    def state(self) -> ConnectionState: ...

    @property
    @abstractmethod
    def harness_id(self) -> HarnessId: ...

    @property
    @abstractmethod
    def spawn_id(self) -> SpawnId: ...

    @property
    @abstractmethod
    def capabilities(self) -> ConnectionCapabilities: ...

    @property
    @abstractmethod
    def session_id(self) -> str | None: ...

    @property
    @abstractmethod
    def subprocess_pid(self) -> int | None: ...

    @abstractmethod
    async def start(self, config: ConnectionConfig, spec: SpecT) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    def health(self) -> bool: ...

    @abstractmethod
    async def send_user_message(self, text: str) -> None: ...

    @abstractmethod
    async def send_interrupt(self) -> None: ...

    @abstractmethod
    async def send_cancel(self) -> None: ...

    @abstractmethod
    def events(self) -> AsyncIterator[HarnessEvent]: ...
```

Concrete connections bind their spec subclass:

```python
# src/meridian/lib/harness/connections/claude_ws.py
class ClaudeConnection(HarnessConnection[ClaudeLaunchSpec]):
    async def start(
        self,
        config: ConnectionConfig,
        spec: ClaudeLaunchSpec,
    ) -> None:
        # No isinstance check. spec IS a ClaudeLaunchSpec at the type
        # level. spec.appended_system_prompt is directly accessible.
        ...
```

```python
# src/meridian/lib/harness/connections/codex_ws.py
class CodexConnection(HarnessConnection[CodexLaunchSpec]):
    async def start(
        self,
        config: ConnectionConfig,
        spec: CodexLaunchSpec,
    ) -> None:
        # spec.sandbox_mode and spec.approval_mode are directly
        # accessible. The projection function uses them.
        ...
```

```python
# src/meridian/lib/harness/connections/opencode_http.py
class OpenCodeConnection(HarnessConnection[OpenCodeLaunchSpec]):
    # Now inherits. M8 resolved.
    async def start(
        self,
        config: ConnectionConfig,
        spec: OpenCodeLaunchSpec,
    ) -> None:
        ...
```

The `HarnessLifecycle`, `HarnessSender`, `HarnessReceiver` runtime_checkable Protocols remain as structural Protocols for any callers that want to type-check against one of the facets, but the concrete connection classes inherit from `HarnessConnection[SpecT]` so the full interface is enforced.

## Dispatch Boundary

The dispatch site — `SpawnManager.start_spawn` and the streaming runner — cannot be fully type-safe because the concrete harness is only known at runtime via `HarnessId`. This is a fundamental limitation: a mapping keyed by runtime id erases type information.

The correct shape is **one declared cast at the dispatch boundary**, with everything downstream of that boundary fully typed:

```python
# src/meridian/lib/streaming/spawn_manager.py
from typing import cast

class SpawnManager:
    async def start_spawn(
        self,
        config: ConnectionConfig,
        spec: ResolvedLaunchSpec,  # any subclass — dispatch uses harness_id
    ) -> HarnessConnection[ResolvedLaunchSpec]:
        connection_cls = get_connection_class(config.harness_id)
        connection = connection_cls()
        # Declared unsafe cast: the connection class and spec subclass
        # are known to match because they were both produced from the
        # same harness_id via the registries. This is the single place
        # that assertion lives.
        await connection.start(config, cast(Any, spec))
        return cast("HarnessConnection[ResolvedLaunchSpec]", connection)
```

The dispatch-site cast is the only escape hatch. It is:
1. **Declared** — it uses `cast(...)` with a clear comment explaining the runtime invariant.
2. **Localized** — one place in the codebase, not scattered across every connection adapter.
3. **Paired** — the registry has a runtime assertion that paired registration of an adapter and its connection matches on spec type.

Downstream of this boundary, every concrete connection's `start()` sees a statically-typed spec. No isinstance, no runtime spec-subclass checks, no silent drops.

### Paired Registry

To make the dispatch-site cast safe at runtime, the connection registry is paired with the adapter registry. Registration requires passing both together:

```python
# src/meridian/lib/harness/registry.py
@dataclass(frozen=True)
class HarnessBundle(Generic[SpecT]):
    harness_id: HarnessId
    adapter: HarnessAdapter[SpecT]
    connection_cls: type[HarnessConnection[SpecT]]
    spec_cls: type[SpecT]

def register_harness_bundle(bundle: HarnessBundle[SpecT]) -> None: ...

def get_harness_bundle(harness_id: HarnessId) -> HarnessBundle[ResolvedLaunchSpec]: ...
```

Registration sites:

```python
register_harness_bundle(HarnessBundle(
    harness_id=HarnessId.CLAUDE,
    adapter=ClaudeAdapter(),
    connection_cls=ClaudeConnection,
    spec_cls=ClaudeLaunchSpec,
))
```

The bundle guarantees that the adapter's factory, the connection class, and the declared spec class all line up for a given `HarnessId`. Dispatch becomes:

```python
bundle = get_harness_bundle(config.harness_id)
spec = bundle.adapter.resolve_launch_spec(params, perms)
connection = bundle.connection_cls()
await connection.start(config, cast(Any, spec))  # declared boundary
```

The `spec_cls` field lets the bundle assert at runtime (in tests and at registration) that `isinstance(spec, bundle.spec_cls)` — a sanity check that confirms the factory returns the advertised subclass. This runs once per launch, costs nothing, and catches a class of future regression where someone changes the factory return type without updating the bundle.

## What Isinstance Branching Cost

The post-impl review surfaced three independent failure modes that isinstance branching enabled:

1. **Generic base specs reaching concrete adapters.** The `spawn_manager.py:99` fallback (`spec or ResolvedLaunchSpec(prompt=config.prompt)`) and the `BaseSubprocessHarness` default factory both produce generic `ResolvedLaunchSpec` instances. In a Protocol-typed world the type checker can't distinguish them from subclasses, so every connection's isinstance branch silently filters out every harness-specific field.

2. **Signature drift goes undetected.** `OpenCodeConnection` (M8) doesn't inherit from `HarnessConnection`. Because the Protocol is `runtime_checkable`, isinstance checks pass structurally at runtime, but adding a method to the Protocol doesn't force OpenCodeConnection to implement it. Silent drift.

3. **Refactoring is unsafe.** Renaming a field on `ClaudeLaunchSpec` or adding a new one cannot be guided by the type checker in the isinstance block — the block is gated by a runtime type test, and pyright happily narrows to "maybe this attribute, maybe not." Refactors miss entire code paths.

All three vanish when the generic type binding is honest: `ClaudeConnection.start(config, spec: ClaudeLaunchSpec)` has no ambiguity, the Protocol is enforced via inheritance, and renames flow through every consumer.

## Migration Shape

The typed refactor lands in one phase, not incrementally, because partial typing leaks. The phase order is:

1. Introduce `SpecT` TypeVar and generic Protocol in `adapter.py`.
2. Convert `HarnessConnection` from runtime Protocol to generic ABC in `connections/base.py`.
3. Update each concrete adapter class declaration to `HarnessAdapter[XxxLaunchSpec]`.
4. Update each concrete connection class declaration to `HarnessConnection[XxxLaunchSpec]`.
5. Delete `BaseSubprocessHarness.resolve_launch_spec`.
6. Delete isinstance branches in every connection's `start()` / `_build_command()` / `_thread_bootstrap_request()` / `_create_session()`.
7. Delete `spawn_manager.py:99` fallback.
8. Introduce `HarnessBundle` + paired registry; update dispatch.
9. Delete the old `_CONNECTION_REGISTRY` keyed on `HarnessId`.

Each step is a pyright-verifiable checkpoint — the build passes only when all isinstance drops are replaced with typed field access. Planner phases this decomposition.

## Interaction with Other Design Docs

- **Spec factory rules** ([launch-spec.md](launch-spec.md)) — the abstract method signature this doc specifies. Field ownership lives there.
- **Transport projections** ([transport-projections.md](transport-projections.md)) — each projection function receives a concrete spec subclass, not a generic one. The projection signature is guaranteed by this doc's type contract.
- **Permission pipeline** ([permission-pipeline.md](permission-pipeline.md)) — `PermissionResolver` is non-optional in the adapter signature. That decision happens there; this doc only references it.
- **Runner shared core** ([runner-shared-core.md](runner-shared-core.md)) — the dispatch-boundary cast lives inside the shared launch context so there is one place, not two.
