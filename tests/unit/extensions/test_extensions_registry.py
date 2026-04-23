"""Unit tests for extension command registry behavior."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from meridian.lib.extensions.registry import (
    ExtensionCommandRegistry,
    build_first_party_registry,
    get_first_party_registry,
)
from meridian.lib.extensions.types import (
    ExtensionCommandSpec,
    ExtensionJSONResult,
    ExtensionSurface,
)


class _ArgsModel(BaseModel):
    value: str = "ok"


class _ResultModel(BaseModel):
    done: bool = True


async def _handler(
    args: dict[str, Any],
    context: Any,
    services: Any,
) -> ExtensionJSONResult:
    del args, context, services
    return ExtensionJSONResult(payload={})


def _make_spec(
    *,
    extension_id: str = "meridian.test",
    command_id: str = "ping",
    first_party: bool = True,
    surfaces: frozenset[ExtensionSurface] = frozenset({ExtensionSurface.HTTP}),
) -> ExtensionCommandSpec:
    return ExtensionCommandSpec(
        extension_id=extension_id,
        command_id=command_id,
        summary="test command",
        args_schema=_ArgsModel,
        result_schema=_ResultModel,
        handler=_handler,
        surfaces=surfaces,
        first_party=first_party,
    )


def test_duplicate_fqid_raises_value_error() -> None:
    registry = ExtensionCommandRegistry()
    spec = _make_spec()
    registry.register(spec)

    with pytest.raises(ValueError, match="Duplicate extension command"):
        registry.register(spec)


@pytest.mark.parametrize(
    "surfaces",
    [
        frozenset({ExtensionSurface.CLI}),
        frozenset({ExtensionSurface.MCP}),
        frozenset({ExtensionSurface.ALL}),
    ],
)
def test_non_first_party_cli_or_mcp_is_rejected(
    surfaces: frozenset[ExtensionSurface],
) -> None:
    registry = ExtensionCommandRegistry()
    spec = _make_spec(first_party=False, surfaces=surfaces)

    with pytest.raises(
        ValueError,
        match="cannot expose CLI or MCP surfaces",
    ):
        registry.register(spec)


def test_get_first_party_registry_returns_singleton_instance() -> None:
    first = get_first_party_registry()
    second = get_first_party_registry()

    assert first is second


def test_build_first_party_registry_returns_fresh_instances() -> None:
    first = build_first_party_registry()
    second = build_first_party_registry()

    assert first is not second
    assert len(first) == 3
    assert len(second) == 3


def test_list_for_surface_filters_by_requested_surface() -> None:
    registry = ExtensionCommandRegistry()
    cli_spec = _make_spec(
        command_id="cli_only",
        surfaces=frozenset({ExtensionSurface.CLI}),
    )
    mcp_spec = _make_spec(
        command_id="mcp_only",
        surfaces=frozenset({ExtensionSurface.MCP}),
    )
    all_spec = _make_spec(
        command_id="all_surfaces",
        surfaces=frozenset({ExtensionSurface.ALL}),
    )
    http_spec = _make_spec(
        extension_id="third.party",
        command_id="http_only",
        first_party=False,
        surfaces=frozenset({ExtensionSurface.HTTP}),
    )
    for spec in (cli_spec, mcp_spec, all_spec, http_spec):
        registry.register(spec)

    cli_ids = {spec.command_id for spec in registry.list_for_surface(ExtensionSurface.CLI)}
    http_ids = {spec.command_id for spec in registry.list_for_surface(ExtensionSurface.HTTP)}

    assert cli_ids == {"cli_only", "all_surfaces"}
    assert http_ids == {"all_surfaces", "http_only"}


def test_command_spec_fqid_property() -> None:
    spec = _make_spec(extension_id="meridian.sessions", command_id="archiveSpawn")

    assert spec.fqid == "meridian.sessions.archiveSpawn"
