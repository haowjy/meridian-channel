"""Workbench/ping first-party extension commands."""

from __future__ import annotations

from typing import Any

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


class PingArgs(BaseModel):
    """No args for ping."""


class PingResult(BaseModel):
    """Result payload for ping."""

    ok: bool


async def ping_handler(
    args: dict[str, Any],
    context: ExtensionInvocationContext,
    services: ExtensionCommandServices,
) -> ExtensionResult:
    """Simple health check command."""

    _ = (args, context, services)
    return ExtensionJSONResult(payload={"ok": True})


PING_SPEC = ExtensionCommandSpec(
    extension_id="meridian.workbench",
    command_id="ping",
    summary="Health check for extension system",
    args_schema=PingArgs,
    result_schema=PingResult,
    handler=ping_handler,
    surfaces=frozenset(
        {
            ExtensionSurface.CLI,
            ExtensionSurface.MCP,
            ExtensionSurface.HTTP,
        }
    ),
    first_party=True,
    requires_app_server=True,
)
