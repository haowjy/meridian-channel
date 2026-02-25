"""Operation registry shared by CLI, MCP, and DirectAdapter surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


@dataclass(frozen=True, slots=True)
class OperationSpec(Generic[InputT, OutputT]):
    """Single source of truth for an operation exposed on both surfaces."""

    name: str
    handler: Callable[[InputT], Coroutine[Any, Any, OutputT]]
    input_type: type[InputT]
    output_type: type[OutputT]
    cli_group: str
    cli_name: str
    mcp_name: str
    description: str
    version: str = "1"
    sync_handler: Callable[[InputT], OutputT] | None = None
    cli_only: bool = False
    mcp_only: bool = False


_REGISTRY: dict[str, OperationSpec[Any, Any]] = {}


def operation(spec: OperationSpec[InputT, OutputT]) -> OperationSpec[InputT, OutputT]:
    """Register an operation and guard against duplicates."""

    if spec.cli_only and spec.mcp_only:
        raise ValueError(f"Operation '{spec.name}' cannot be both cli_only and mcp_only")
    if spec.name in _REGISTRY:
        raise ValueError(
            f"Duplicate operation name '{spec.name}': already registered by "
            f"{_REGISTRY[spec.name].handler}"
        )
    _REGISTRY[spec.name] = spec
    return spec


def get_all_operations() -> list[OperationSpec[Any, Any]]:
    """Return all registered operations sorted by canonical name."""

    return [_REGISTRY[name] for name in sorted(_REGISTRY)]


def get_operation(name: str) -> OperationSpec[Any, Any]:
    """Fetch one operation spec by canonical name."""

    return _REGISTRY[name]


def _bootstrap_operation_modules() -> None:
    # Imported lazily to keep the registry as the single source of truth while
    # allowing operation modules to self-register via `operation(...)`.
    import meridian.lib.ops.context as context_ops
    import meridian.lib.ops.diag as diag_ops
    import meridian.lib.ops.migrate as migrate_ops
    import meridian.lib.ops.models as models_ops
    import meridian.lib.ops.run as run_ops
    import meridian.lib.ops.skills as skills_ops
    import meridian.lib.ops.workspace as workspace_ops

    _ = (
        context_ops,
        diag_ops,
        migrate_ops,
        models_ops,
        run_ops,
        skills_ops,
        workspace_ops,
    )


_bootstrap_operation_modules()
