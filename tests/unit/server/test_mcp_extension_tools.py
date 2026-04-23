"""Unit tests for MCP extension tool surface gating."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

import meridian.server.main as server_main
from meridian.lib.extensions.context import (
    ExtensionCommandServices,
    ExtensionInvocationContext,
)
from meridian.lib.extensions.registry import ExtensionCommandRegistry
from meridian.lib.extensions.types import (
    ExtensionCommandSpec,
    ExtensionJSONResult,
    ExtensionSurface,
)
from meridian.server.main import extension_invoke


class _StubArgs(BaseModel):
    spawn_id: str


class _StubResult(BaseModel):
    ok: bool


async def _stub_handler(
    args: dict[str, Any],
    context: ExtensionInvocationContext,
    services: ExtensionCommandServices,
) -> ExtensionJSONResult:
    _ = (args, context, services)
    return ExtensionJSONResult(payload={"ok": True})


def _make_spec(
    *,
    surfaces: frozenset[ExtensionSurface],
    requires_app_server: bool = False,
) -> ExtensionCommandSpec:
    return ExtensionCommandSpec(
        extension_id="meridian.test",
        command_id="gatedCmd",
        summary="test surface gate",
        args_schema=_StubArgs,
        result_schema=_StubResult,
        handler=_stub_handler,
        surfaces=surfaces,
        first_party=True,
        requires_app_server=requires_app_server,
    )


@pytest.mark.asyncio
async def test_mcp_surface_gate_rejects_non_mcp_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _make_spec(surfaces=frozenset({ExtensionSurface.HTTP}))
    registry = ExtensionCommandRegistry()
    registry.register(spec)
    monkeypatch.setattr(server_main, "build_first_party_registry", lambda: registry)

    result = await extension_invoke(fqid=spec.fqid, args={"spawn_id": "p1"})

    assert result["status"] == "error"
    assert result["code"] == "surface_not_allowed"
