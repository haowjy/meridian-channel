"""Unit tests for extension discovery projections and route construction."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from meridian.lib.app.extension_routes import (
    make_discovery_routes,
    project_command,
    project_extensions,
)
from meridian.lib.extensions.registry import ExtensionCommandRegistry
from meridian.lib.extensions.types import (
    ExtensionCommandSpec,
    ExtensionJSONResult,
    ExtensionSurface,
)


class _ArgsModel(BaseModel):
    spawn_id: str


class _ResultModel(BaseModel):
    archived: bool


async def _handler(
    args: dict[str, Any],
    context: Any,
    services: Any,
) -> ExtensionJSONResult:
    _ = (args, context, services)
    return ExtensionJSONResult(payload={"archived": True})


def _make_spec(
    *,
    extension_id: str,
    command_id: str,
    surfaces: frozenset[ExtensionSurface],
) -> ExtensionCommandSpec:
    return ExtensionCommandSpec(
        extension_id=extension_id,
        command_id=command_id,
        summary=f"summary for {command_id}",
        args_schema=_ArgsModel,
        result_schema=_ResultModel,
        handler=_handler,
        surfaces=surfaces,
        first_party=True,
        requires_app_server=True,
    )


def test_project_command_serializes_schema_and_surface_values() -> None:
    spec = _make_spec(
        extension_id="meridian.sessions",
        command_id="archiveSpawn",
        surfaces=frozenset({ExtensionSurface.HTTP, ExtensionSurface.MCP}),
    )

    projection = project_command(spec)

    assert projection.command_id == "archiveSpawn"
    assert projection.summary == "summary for archiveSpawn"
    assert projection.args_schema["type"] == "object"
    assert projection.output_schema["type"] == "object"
    assert set(projection.surfaces) == {"http", "mcp"}
    assert projection.requires_app_server is True


def test_project_extensions_groups_by_extension_id_and_sorts_extensions() -> None:
    registry = ExtensionCommandRegistry()
    registry.register(
        _make_spec(
            extension_id="zeta.ext",
            command_id="one",
            surfaces=frozenset({ExtensionSurface.HTTP}),
        )
    )
    registry.register(
        _make_spec(
            extension_id="alpha.ext",
            command_id="first",
            surfaces=frozenset({ExtensionSurface.HTTP}),
        )
    )
    registry.register(
        _make_spec(
            extension_id="alpha.ext",
            command_id="second",
            surfaces=frozenset({ExtensionSurface.HTTP}),
        )
    )

    projections = project_extensions(registry)

    assert [item.extension_id for item in projections] == ["alpha.ext", "zeta.ext"]
    alpha = projections[0]
    assert alpha.extension_id == "alpha.ext"
    assert {command.command_id for command in alpha.commands} == {"first", "second"}


def test_make_discovery_routes_registers_static_before_dynamic_paths() -> None:
    registry = ExtensionCommandRegistry()
    registry.register(
        _make_spec(
            extension_id="meridian.workbench",
            command_id="ping",
            surfaces=frozenset({ExtensionSurface.ALL}),
        )
    )

    routes = make_discovery_routes(registry)
    route_paths = [route.path for route in routes]

    assert route_paths == [
        "/api/extensions",
        "/api/extensions/manifest-hash",
        "/api/extensions/operations/{operation_id}",
        "/api/extensions/{extension_id}",
        "/api/extensions/{extension_id}/commands",
    ]
