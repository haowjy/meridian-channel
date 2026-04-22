"""Core extension system types and handler protocol contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from meridian.lib.extensions.context import (
    ExtensionCommandServices,
    ExtensionInvocationContext,
)


@runtime_checkable
class ExtensionHandler(Protocol):
    """3-arg contract all extension handlers must implement."""

    async def __call__(
        self,
        args: dict[str, Any],
        context: ExtensionInvocationContext,
        services: ExtensionCommandServices,
    ) -> ExtensionResult: ...


class ExtensionSurface(StrEnum):
    """Surfaces where an extension command can be exposed."""

    HTTP = "http"
    CLI = "cli"
    MCP = "mcp"
    ALL = "*"


class ExtensionCommandSpec(BaseModel):
    """Specification for an extension command."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    extension_id: str = Field(
        description="Extension namespace, e.g. 'meridian.sessions'",
    )
    command_id: str = Field(
        description="Command name within extension, e.g. 'archiveSpawn'",
    )
    summary: str = Field(description="One-line description for CLI/MCP help")
    args_schema: type[BaseModel] = Field(
        description="Pydantic model for input validation",
    )
    result_schema: type[BaseModel] = Field(description="Pydantic model for output")
    handler: ExtensionHandler
    surfaces: frozenset[ExtensionSurface] = Field(
        default=frozenset({ExtensionSurface.ALL}),
    )
    first_party: bool = Field(default=False)
    requires_app_server: bool = Field(
        default=True,
        description="If True, command only runs when app server is available",
    )
    required_capabilities: frozenset[str] = Field(default=frozenset())

    @property
    def fqid(self) -> str:
        """Fully qualified command ID: extension_id.command_id."""

        return f"{self.extension_id}.{self.command_id}"


class ExtensionJSONResult(BaseModel):
    """Successful command result with JSON-serializable payload."""

    model_config = ConfigDict(frozen=True)

    payload: dict[str, Any]


class ExtensionErrorResult(BaseModel):
    """Command error with machine-readable code and human message."""

    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    details: dict[str, Any] | None = None


type ExtensionResult = ExtensionJSONResult | ExtensionErrorResult


__all__ = [
    "ExtensionCommandServices",
    "ExtensionCommandSpec",
    "ExtensionErrorResult",
    "ExtensionHandler",
    "ExtensionInvocationContext",
    "ExtensionJSONResult",
    "ExtensionResult",
    "ExtensionSurface",
]
