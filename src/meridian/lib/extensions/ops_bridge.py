"""Bridge OperationSpec operations to ExtensionCommandSpec."""

from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel

from meridian.lib.extensions.context import (
    ExtensionCommandServices,
    ExtensionInvocationContext,
)
from meridian.lib.extensions.types import (
    ExtensionCommandSpec,
    ExtensionJSONResult,
    ExtensionResult,
    ExtensionSurface,
)
from meridian.lib.ops.manifest import OperationSpec, get_all_operations


def _map_surfaces(op: OperationSpec[Any, Any]) -> frozenset[ExtensionSurface]:
    """Map OperationSpec surfaces to ExtensionSurface with HTTP exposure."""
    if "cli" in op.surfaces and "mcp" in op.surfaces:
        return frozenset({ExtensionSurface.ALL})
    if "cli" in op.surfaces:
        return frozenset({ExtensionSurface.CLI, ExtensionSurface.HTTP})
    return frozenset({ExtensionSurface.MCP, ExtensionSurface.HTTP})


def _derive_extension_id(op: OperationSpec[Any, Any]) -> str:
    """Derive extension_id from operation name."""
    parts = op.name.split(".", 1)
    return f"meridian.{parts[0]}"


def _derive_command_id(op: OperationSpec[Any, Any]) -> str:
    """Derive command_id from operation name."""
    parts = op.name.split(".", 1)
    return parts[1] if len(parts) > 1 else parts[0]


def _create_handler(op: OperationSpec[Any, Any]):
    """Create an extension handler that wraps an OperationSpec handler."""

    async def handler(
        args: dict[str, Any],
        context: ExtensionInvocationContext,
        services: ExtensionCommandServices,
    ) -> ExtensionResult:
        _ = (context, services)  # Operations don't use extension context
        input_obj = op.input_type(**args)
        result = await op.handler(input_obj)
        if hasattr(result, "to_wire"):
            return ExtensionJSONResult(payload=result.to_wire())
        if isinstance(result, BaseModel):
            return ExtensionJSONResult(payload=result.model_dump())
        return ExtensionJSONResult(payload={"result": result})

    return handler


def wrap_operation(op: OperationSpec[Any, Any]) -> ExtensionCommandSpec:
    """Wrap an OperationSpec as an ExtensionCommandSpec."""
    return ExtensionCommandSpec(
        extension_id=_derive_extension_id(op),
        command_id=_derive_command_id(op),
        summary=op.description,
        args_schema=cast("type[BaseModel]", op.input_type),
        result_schema=cast("type[BaseModel]", op.output_type),
        handler=_create_handler(op),
        surfaces=_map_surfaces(op),
        first_party=True,
        requires_app_server=False,
    )


def get_wrapped_operations() -> list[ExtensionCommandSpec]:
    """Wrap all OperationSpec operations as ExtensionCommandSpec commands."""
    return [wrap_operation(op) for op in get_all_operations()]


def register_operations(registry: Any) -> None:
    """Register all wrapped operations in a registry."""
    for spec in get_wrapped_operations():
        registry.register(spec)
