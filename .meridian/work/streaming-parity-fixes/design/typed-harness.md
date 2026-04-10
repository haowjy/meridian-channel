# Typed Harness Contract

## Purpose

Bind each adapter and connection to a concrete launch-spec subtype so harness dispatch cannot silently downcast into generic behavior. Runtime and static enforcement are both explicit.

## Leaf Types (`launch_types.py`)

```python
# src/meridian/lib/harness/launch_types.py
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generic, Protocol, TypeVar

SpecT = TypeVar("SpecT", bound="ResolvedLaunchSpec")

class PermissionResolver(Protocol):
    @property
    def config(self) -> PermissionConfig: ...
    def resolve_flags(self, harness: HarnessId) -> tuple[str, ...]: ...


class ResolvedLaunchSpec(BaseModel):
    ...


@dataclass(frozen=True)
class PreflightResult:
    expanded_passthrough_args: tuple[str, ...]
    extra_env: dict[str, str] = field(default_factory=dict)
    extra_cwd_overrides: dict[str, str] = field(default_factory=dict)
```

`adapter.py` and `launch_spec.py` both import from this leaf module to avoid cycles.

## Adapter Contract

Two mechanisms are used and they have different roles:

- `@runtime_checkable Protocol` (`HarnessAdapter[SpecT]`) for structural type checking in pyright.
- `abc.ABC` abstract methods (`BaseSubprocessHarness(Generic[SpecT], ABC)`) for runtime instantiation rejection.

Protocol conformance does not raise `TypeError` at instantiation. ABC abstract-method enforcement does.

```python
# src/meridian/lib/harness/adapter.py
@runtime_checkable
class HarnessAdapter(Protocol, Generic[SpecT]):
    @property
    def id(self) -> HarnessId: ...

    def resolve_launch_spec(self, run: SpawnParams, perms: PermissionResolver) -> SpecT: ...

    def preflight(
        self,
        *,
        execution_cwd: Path,
        child_cwd: Path,
        passthrough_args: tuple[str, ...],
    ) -> PreflightResult: ...


class BaseSubprocessHarness(Generic[SpecT], ABC):
    @abstractmethod
    def resolve_launch_spec(self, run: SpawnParams, perms: PermissionResolver) -> SpecT:
        ...

    def preflight(
        self,
        *,
        execution_cwd: Path,
        child_cwd: Path,
        passthrough_args: tuple[str, ...],
    ) -> PreflightResult:
        return PreflightResult(expanded_passthrough_args=passthrough_args)
```

`ClaudeAdapter.preflight(...)` performs Claude-specific parent-permission and `--add-dir` expansion. `CodexAdapter` and `OpenCodeAdapter` use the base default.

## Connection Contract

Use one interface: `HarnessConnection[SpecT]` ABC. Facet protocols (`HarnessLifecycle`, `HarnessSender`, `HarnessReceiver`) are removed in v2 to avoid duplicate method surfaces drifting.

```python
class HarnessConnection(Generic[SpecT], ABC):
    @abstractmethod
    async def start(self, config: ConnectionConfig, spec: SpecT) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def send_user_message(self, text: str) -> None: ...

    @abstractmethod
    async def send_interrupt(self) -> None: ...

    @abstractmethod
    async def send_cancel(self) -> None: ...

    @abstractmethod
    def events(self) -> AsyncIterator[HarnessEvent]: ...
```

## Dispatch Boundary (authoritative site)

The single cast boundary is in `SpawnManager.start_spawn` dispatch, not in `prepare_launch_context`.

```python
from typing import cast

async def dispatch_start(
    bundle: HarnessBundle[SpecT],
    config: ConnectionConfig,
    spec: ResolvedLaunchSpec,
) -> HarnessConnection[SpecT]:
    if not isinstance(spec, bundle.spec_cls):
        raise TypeError(
            f"HarnessBundle invariant violated: adapter for "
            f"{bundle.harness_id} returned {type(spec).__name__}, "
            f"expected {bundle.spec_cls.__name__}"
        )
    connection = bundle.connection_cls()
    await connection.start(config, cast(SpecT, spec))
    return connection
```

This runtime guard is the S002 runtime trigger. It is the only allowed boundary-type guard.

Inside concrete `Connection.start(...)` methods, behavior-switching `isinstance` branches are disallowed.

## Import Topology

```
launch_types.py   (SpawnParams, PermissionResolver, SpecT, ResolvedLaunchSpec, PreflightResult)
    ↑
    ├── adapter.py       (HarnessAdapter[SpecT], BaseSubprocessHarness)
    └── launch_spec.py   (Claude/Codex/OpenCodeLaunchSpec)
         ↑
         └── projections/*.py
              ↑
              └── connections/*.py and harness adapters
```

This is the acyclic dependency DAG used by S031.

## Migration Shape

1. Introduce `launch_types.py` and move shared leaf types there.
2. Make `BaseSubprocessHarness` an `ABC` and `resolve_launch_spec` abstract.
3. Add `preflight(...) -> PreflightResult` to `HarnessAdapter` and base class.
4. Collapse connection facet protocols into `HarnessConnection[SpecT]` ABC.
5. Convert concrete adapters/connections to generic bindings.
6. Introduce `HarnessBundle` registry and dispatch runtime guard.
7. Delete legacy fallback (`spec or ResolvedLaunchSpec(...)`).
8. Audit `BaseSubprocessHarness` default methods (`fork_session`, `owns_untracked_session`, `blocked_child_env_vars`, `seed_session`, `filter_launch_content`, `detect_primary_session_id`, `mcp_config`, `extract_report`, `resolve_session_file`, `run_prompt_policy`, `build_adhoc_agent_payload`) and delete methods that are dead or universally overridden.

## Interaction with Other Docs

- [launch-spec.md](launch-spec.md): concrete spec fields and construction-side accounting.
- [transport-projections.md](transport-projections.md): projection accounting and wire contracts.
- [runner-shared-core.md](runner-shared-core.md): shared context assembly calls `adapter.preflight(...)`; it does not host dispatch casting.
