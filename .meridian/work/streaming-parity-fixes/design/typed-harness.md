# Typed Harness Contract

## Purpose

Bind each adapter, connection, and extractor to a concrete launch-spec subtype so harness dispatch cannot silently downcast into generic behavior. Runtime and static enforcement are both explicit.

Revision round 3 reframes the invariants this doc carries: every check here exists to protect meridian's own internal coordination logic from drift. Nothing here validates or polices the content of user-supplied `extra_args`, permission combinations, or harness decisions.

## Module: `launch/launch_types.py`

```python
# src/meridian/lib/launch/launch_types.py
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Generic, Protocol, TypeVar
from pydantic import BaseModel, ConfigDict, model_validator

SpecT = TypeVar("SpecT", bound="ResolvedLaunchSpec")


class PermissionResolver(Protocol):
    """Transport-neutral permission intent.

    Revision round 3 (K4): `resolve_flags` no longer takes a harness parameter.
    The resolver exposes abstract intent via `config`; projections translate
    that intent into harness-specific wire format. This prevents resolvers
    from re-introducing `if harness == CLAUDE` branching internally.
    """

    @property
    def config(self) -> PermissionConfig: ...

    def resolve_flags(self) -> tuple[str, ...]:
        """Return harness-agnostic flag hints (or `()`).

        The preferred shape for all v2 resolvers is to return `()` and let
        projections read everything from `config`. `resolve_flags` is kept
        as a deprecated escape hatch for legacy resolvers that still emit
        pre-formatted flags; its output is passed through the projection's
        harness-specific formatter and may be dropped entirely in a later
        revision. Never branch on harness id inside a resolver.
        """
        ...


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

    # Passthrough args — forwarded verbatim to the harness. Never stripped
    # or rewritten by meridian. This is an explicit escape hatch.
    extra_args: tuple[str, ...] = ()

    # Interactive mode
    interactive: bool = False

    # MCP tool specifications. Harness-agnostic list of MCP tool identifiers
    # (or path refs) resolved into harness-specific wire format by each
    # projection. Restored in revision round 3 (D4). Auto-packaging through
    # mars is out of scope for v2; manual configuration via SpawnParams works.
    mcp_tools: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_continue_fork_requires_session(self) -> "ResolvedLaunchSpec":
        if self.continue_fork and not self.continue_session_id:
            raise ValueError("continue_fork=True requires continue_session_id")
        return self


@dataclass(frozen=True)
class PreflightResult:
    """Result of adapter-owned preflight.

    K7: `extra_env` is wrapped in `MappingProxyType` at construction to
    protect meridian's own merge pipeline from downstream mutation.
    """

    expanded_passthrough_args: tuple[str, ...]
    extra_env: MappingProxyType[str, str]

    @classmethod
    def build(
        cls,
        *,
        expanded_passthrough_args: tuple[str, ...],
        extra_env: dict[str, str] | None = None,
    ) -> "PreflightResult":
        return cls(
            expanded_passthrough_args=expanded_passthrough_args,
            extra_env=MappingProxyType(dict(extra_env or {})),
        )
```

`adapter.py`, `launch_spec.py`, `bundle.py`, and the extractor base all import from this leaf module to avoid cycles.

## Bundle Registry (K1, K2)

v2 dispatches on `(harness_id, transport_id)` so adding a new transport for an existing harness (e.g., Claude-over-HTTP) is a one-line addition to an existing bundle's `connections` mapping, not a rewiring of dispatch code.

```python
# src/meridian/lib/harness/bundle.py
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Generic

from meridian.lib.launch.launch_types import SpecT, ResolvedLaunchSpec
from meridian.lib.harness.adapter import HarnessAdapter
from meridian.lib.harness.connections.base import HarnessConnection
from meridian.lib.harness.extractors.base import HarnessExtractor
from meridian.lib.harness.ids import HarnessId, TransportId


@dataclass(frozen=True)
class HarnessBundle(Generic[SpecT]):
    harness_id: HarnessId
    adapter: HarnessAdapter[SpecT]
    spec_cls: type[SpecT]
    extractor: HarnessExtractor[SpecT]
    connections: Mapping[TransportId, type[HarnessConnection[SpecT]]]


_REGISTRY: dict[HarnessId, HarnessBundle[Any]] = {}


def register_harness_bundle(bundle: HarnessBundle[Any]) -> None:
    """Sole mutation site for the harness bundle registry (K2).

    Raises `ValueError` if a bundle for the same `harness_id` is already
    registered. This catches duplicate registrations caused by double-import
    or by two modules claiming the same harness id — failures that would
    otherwise silently change dispatch by last-import-wins.
    """
    if bundle.harness_id in _REGISTRY:
        existing = type(_REGISTRY[bundle.harness_id].adapter).__name__
        incoming = type(bundle.adapter).__name__
        raise ValueError(
            f"duplicate harness bundle for {bundle.harness_id}: "
            f"existing adapter={existing}, incoming adapter={incoming}"
        )
    _REGISTRY[bundle.harness_id] = bundle


def get_harness_bundle(harness_id: HarnessId) -> HarnessBundle[Any]:
    try:
        return _REGISTRY[harness_id]
    except KeyError:
        raise KeyError(f"unknown harness: {harness_id}") from None


def get_connection_cls(
    harness_id: HarnessId,
    transport_id: TransportId,
) -> type[HarnessConnection[Any]]:
    bundle = get_harness_bundle(harness_id)
    try:
        return bundle.connections[transport_id]
    except KeyError:
        raise KeyError(
            f"harness {harness_id} has no connection for transport {transport_id}"
        ) from None
```

### Bundle registration bootstrapping

`harness/__init__.py` imports every `claude`, `codex`, and `opencode` adapter module eagerly so `register_harness_bundle(...)` is always invoked before any dispatch site reads the registry. The eager-import edge is part of the DAG in [§Import Topology](#import-topology).

### Import-time invariants enforced by bundle / registry

- Duplicate `register_harness_bundle(bundle)` with the same `harness_id` raises `ValueError` (S039).
- Every bundle's `connections` mapping is non-empty.
- Every bundle's `adapter` is a `HarnessAdapter[SpecT]` and its `spec_cls` matches the generic binding at import time (Protocol runtime-check).
- Every bundle exposes an `extractor: HarnessExtractor[SpecT]` (K6).

## Adapter Contract (K3, K9)

Two mechanisms are used and they have different roles:

- `@runtime_checkable Protocol` (`HarnessAdapter[SpecT]`) for structural type checking in pyright.
- `abc.ABC` abstract methods (`BaseSubprocessHarness(Generic[SpecT], ABC)`) for runtime instantiation rejection.

Protocol conformance does not raise `TypeError` at instantiation. ABC abstract-method enforcement does. K3 requires that the Protocol and ABC expose the same required method set so a subclass cannot be ABC-instantiable while Protocol-noncompliant.

```python
# src/meridian/lib/harness/adapter.py
@runtime_checkable
class HarnessAdapter(Protocol, Generic[SpecT]):
    @property
    def id(self) -> HarnessId: ...

    @property
    def handled_fields(self) -> frozenset[str]:
        """SpawnParams fields this adapter maps onto its spec (K9).

        The union of every registered adapter's `handled_fields` must equal
        `SpawnParams.model_fields`. An import-time guard in
        `harness/launch_spec.py` raises `ImportError` on drift.
        """
        ...

    def resolve_launch_spec(self, run: SpawnParams, perms: PermissionResolver) -> SpecT: ...

    def preflight(
        self,
        *,
        execution_cwd: Path,
        child_cwd: Path,
        passthrough_args: tuple[str, ...],
    ) -> PreflightResult: ...


class BaseSubprocessHarness(Generic[SpecT], ABC):
    @property
    @abstractmethod
    def id(self) -> HarnessId:
        """Harness identifier. Marked abstract so subclasses that forget
        to declare `id` fail at instantiation instead of crashing deep in
        dispatch with `AttributeError` (K3).
        """
        ...

    @property
    @abstractmethod
    def handled_fields(self) -> frozenset[str]:
        """Abstract so every concrete adapter is forced to declare which
        SpawnParams fields it maps (K9). Import-time check in
        `harness/launch_spec.py` aggregates these across all adapters."""
        ...

    @abstractmethod
    def resolve_launch_spec(self, run: SpawnParams, perms: PermissionResolver) -> SpecT: ...

    def preflight(
        self,
        *,
        execution_cwd: Path,
        child_cwd: Path,
        passthrough_args: tuple[str, ...],
    ) -> PreflightResult:
        return PreflightResult.build(expanded_passthrough_args=passthrough_args)
```

`ClaudeAdapter.preflight(...)` performs Claude-specific parent-permission and `--add-dir` expansion. `CodexAdapter` and `OpenCodeAdapter` use the base default.

A unit test reconciles `HarnessAdapter` Protocol attributes against the abstract method set on `BaseSubprocessHarness`. If they drift, the test fails (S040).

## Connection Contract (K8)

One interface: `HarnessConnection[SpecT]` ABC. Facet protocols (`HarnessLifecycle`, `HarnessSender`, `HarnessReceiver`) are removed in v2 to avoid duplicate method surfaces drifting.

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

### Cancel / Interrupt / SIGTERM Semantics (K8)

| Method / Signal | Trigger | Idempotency | Terminal status | Ordering guarantee |
|---|---|---|---|---|
| `send_cancel()` | Explicit cancel (user API, runner cleanup) | Idempotent — repeated calls after the first collapse to a no-op | Single `cancelled` terminal spawn status | Cancel event is enqueued before any `send_error` awaited by the cancel path |
| `send_interrupt()` | Mid-turn interrupt (soft stop) | Idempotent — repeated calls collapse to a no-op | Converges to `cancelled` if the harness does not resume; otherwise `completed` on natural finish | Interrupt event ordering is preserved relative to subsequent send_user_message calls |
| Runner SIGTERM / SIGINT | Host signal | Translated into exactly one `send_cancel()` invocation on every active connection | `cancelled` on terminal reconciliation | Signal handler records cancellation intent before connection unwind; reconciliation finalizes status crash-only |

Invariants:

- A single spawn cannot produce more than one terminal status. If cancel races completion, the first persisted terminal status wins and subsequent terminal writes are dropped by the spawn store's atomic write path.
- `send_cancel` and `send_interrupt` MUST be safe to call from signal handlers (no blocking I/O, no allocation-heavy operations).
- Cancellation event emission is exactly-once per spawn, ordered before any subsequent error-emission on the same connection.
- Runner-level signal handling is transport-neutral: the runner does not know whether the harness is subprocess or streaming; it calls `send_cancel` on the connection and relies on crash-only reconciliation for cleanup.

Scenarios S041 and S042 exercise cancel / interrupt parity across subprocess and streaming transports.

## Dispatch Boundary (authoritative site) — K1

The single cast boundary is in `SpawnManager.start_spawn` dispatch, not in `prepare_launch_context`.

```python
from typing import cast

async def dispatch_start(
    *,
    harness_id: HarnessId,
    transport_id: TransportId,
    config: ConnectionConfig,
    spec: ResolvedLaunchSpec,
) -> HarnessConnection[Any]:
    bundle = get_harness_bundle(harness_id)
    if not isinstance(spec, bundle.spec_cls):
        raise TypeError(
            f"HarnessBundle invariant violated: adapter for "
            f"{bundle.harness_id} returned {type(spec).__name__}, "
            f"expected {bundle.spec_cls.__name__}"
        )
    try:
        connection_cls = bundle.connections[transport_id]
    except KeyError:
        raise KeyError(
            f"harness {bundle.harness_id} does not support transport {transport_id}"
        ) from None
    connection = connection_cls()
    await connection.start(config, cast(SpecT, spec))
    return connection
```

This runtime guard is the S002 runtime trigger. It is the only allowed boundary-type guard.

Inside concrete `Connection.start(...)` methods, behavior-switching `isinstance` branches are disallowed.

## Extractor Contract (K6)

```python
# src/meridian/lib/harness/extractors/base.py
class HarnessExtractor(Protocol, Generic[SpecT]):
    """Harness-specific event and artifact extraction.

    Used symmetrically by subprocess and streaming runners so that
    session-id detection and report extraction stay transport-neutral.
    Closes the p1385 gap where streaming had no fallback session detection
    via harness-specific project files (Claude project files, Codex rollout
    files, OpenCode logs).
    """

    def detect_session_id_from_event(
        self,
        event: HarnessEvent,
    ) -> str | None:
        """Extract session id from a live event stream frame, if present."""
        ...

    def detect_session_id_from_artifacts(
        self,
        *,
        child_cwd: Path,
        state_root: Path,
    ) -> str | None:
        """Fallback session id detection from harness-specific artifacts.

        Required for every harness. Subprocess was already doing this;
        streaming now has parity via the same extractor.
        """
        ...

    def extract_report(
        self,
        *,
        spec: SpecT,
        child_cwd: Path,
        artifacts_dir: Path,
    ) -> str | None:
        """Extract the final report from post-run artifacts, if produced."""
        ...
```

### Extractor drift guard

`src/meridian/lib/harness/extractors/__init__.py` imports every concrete extractor eagerly and asserts that every registered `HarnessBundle.extractor` is non-None. Missing extractors fail at import. S043 exercises this.

## Import Topology

```
launch/launch_types.py
    ↑
    ├── harness/adapter.py
    ├── harness/launch_spec.py
    ├── harness/connections/base.py
    ├── harness/extractors/base.py
    └── harness/bundle.py
         ↑
         └── launch/context.py

launch/constants.py
    ↑
    ├── launch/context.py
    ├── harness/claude_preflight.py
    └── harness/projections/project_codex_streaming.py

launch/text_utils.py
    ↑
    ├── harness/claude_preflight.py
    └── harness/projections/project_claude.py

harness/projections/_guards.py
    ↑
    ├── harness/projections/project_claude.py
    ├── harness/projections/project_codex_subprocess.py
    ├── harness/projections/project_codex_streaming.py
    ├── harness/projections/project_opencode_subprocess.py
    └── harness/projections/project_opencode_streaming.py

harness/adapter.py
    ↑
    ├── harness/claude.py (uses harness/claude_preflight.py)
    ├── harness/codex.py
    └── harness/opencode.py

harness/launch_spec.py
    ↑
    ├── harness/projections/project_claude.py
    ├── harness/projections/project_codex_subprocess.py
    ├── harness/projections/project_codex_streaming.py
    ├── harness/projections/project_opencode_subprocess.py
    └── harness/projections/project_opencode_streaming.py

harness/extractors/base.py
    ↑
    ├── harness/extractors/claude.py
    ├── harness/extractors/codex.py
    └── harness/extractors/opencode.py

harness/connections/base.py
    ↑
    ├── harness/connections/subprocess.py
    ├── harness/connections/claude_streaming.py
    ├── harness/connections/codex_streaming.py
    └── harness/connections/opencode_streaming.py

harness/errors.py
    ↑
    ├── runner.py
    └── streaming_runner.py

launch/context.py
    ↑
    ├── runner.py
    └── streaming_runner.py

harness/__init__.py
    ↑  (eager imports guarantee registrations + guards always execute)
    ├── harness/claude.py
    ├── harness/codex.py
    ├── harness/opencode.py
    ├── harness/projections/project_claude.py
    ├── harness/projections/project_codex_subprocess.py
    ├── harness/projections/project_codex_streaming.py
    ├── harness/projections/project_opencode_subprocess.py
    ├── harness/projections/project_opencode_streaming.py
    ├── harness/extractors/claude.py
    ├── harness/extractors/codex.py
    └── harness/extractors/opencode.py
```

Revision round 3 removes `harness/projections/_reserved_flags.py` from the topology (D1).

This is the acyclic dependency DAG used by S031. The `harness/__init__.py` eager-import edge (C2) guarantees projection drift guards, extractor drift guards, and bundle registrations all execute before the first dispatch — any import-time error surfaces during package load, not after a dispatch failure.

## Migration Shape

1. Introduce `launch_types.py` and move shared leaf types there.
2. Make `BaseSubprocessHarness` an `ABC`, and mark `id`, `handled_fields`, and `resolve_launch_spec` abstract (K3, K9).
3. Add `preflight(...) -> PreflightResult` to `HarnessAdapter` and base class; wrap `PreflightResult.extra_env` in `MappingProxyType` (K7).
4. Collapse connection facet protocols into `HarnessConnection[SpecT]` ABC; document cancel/interrupt semantics table (K8).
5. Convert concrete adapters/connections/extractors to generic bindings.
6. Introduce `HarnessBundle` registry with `register_harness_bundle()` helper and `(harness_id, transport_id)` dispatch (K1, K2); add extractor to bundle (K6).
7. Delete legacy fallback (`spec or ResolvedLaunchSpec(...)`).
8. Delete reserved-flag machinery (`_RESERVED_*`, `strip_reserved_passthrough`) — do NOT keep in `projections/_reserved_flags.py` (D1).
9. Restore `mcp_tools: tuple[str, ...]` on `ResolvedLaunchSpec` and wire each projection's MCP mapping (D4).
10. Update `PermissionResolver.resolve_flags` signature to drop the `harness` parameter (K4).
11. Add `model_config = ConfigDict(frozen=True)` to `PermissionConfig` (K7).
12. Add eager imports in `harness/__init__.py` and `harness/extractors/__init__.py` (C2).
13. Audit `BaseSubprocessHarness` default methods (`fork_session`, `owns_untracked_session`, `blocked_child_env_vars`, `seed_session`, `filter_launch_content`, `detect_primary_session_id`, `mcp_config`, `extract_report`, `resolve_session_file`, `run_prompt_policy`, `build_adhoc_agent_payload`) and delete methods that are dead or universally overridden. `detect_primary_session_id` and `extract_report` move into `HarnessExtractor`.

## Interaction with Other Docs

- [launch-spec.md](launch-spec.md): concrete spec fields, construction-side accounting, per-adapter `handled_fields` guard.
- [transport-projections.md](transport-projections.md): projection accounting and wire contracts, `mcp_tools` mapping, verbatim `extra_args` forwarding.
- [permission-pipeline.md](permission-pipeline.md): resolver contract (no harness parameter), immutable `PermissionConfig`.
- [runner-shared-core.md](runner-shared-core.md): shared context assembly calls `adapter.preflight(...)`, it does not host dispatch casting; `MERIDIAN_*` sole-producer invariant.
