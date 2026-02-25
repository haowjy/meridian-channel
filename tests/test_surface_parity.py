"""Surface parity checks between registry, CLI, and MCP server."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from meridian.cli.main import get_registered_cli_commands, get_registered_cli_descriptions
from meridian.lib.ops.registry import OperationSpec, get_all_operations, operation
from meridian.server.main import get_registered_mcp_descriptions, get_registered_mcp_tools


async def _dup_async(_: _DupInput) -> _DupOutput:
    return _DupOutput(ok=True)


def _dup_sync(_: _DupInput) -> _DupOutput:
    return _DupOutput(ok=True)


@dataclass(frozen=True, slots=True)
class _DupInput:
    pass


@dataclass(frozen=True, slots=True)
class _DupOutput:
    ok: bool


def test_every_operation_has_both_surfaces() -> None:
    cli_commands = get_registered_cli_commands()
    mcp_tools = get_registered_mcp_tools()

    for op in get_all_operations():
        if not op.cli_only:
            assert op.mcp_name in mcp_tools, (
                f"{op.name} missing MCP tool (set cli_only=True if intentional)"
            )
        if not op.mcp_only:
            assert f"{op.cli_group}.{op.cli_name}" in cli_commands, (
                f"{op.name} missing CLI command (set mcp_only=True if intentional)"
            )


def test_cli_help_matches_mcp_description() -> None:
    cli_descriptions = get_registered_cli_descriptions()
    mcp_descriptions = get_registered_mcp_descriptions()

    for op in get_all_operations():
        if not op.cli_only and not op.mcp_only:
            assert cli_descriptions[op.name] == mcp_descriptions[op.name]


def test_duplicate_operation_name_guard() -> None:
    with pytest.raises(ValueError, match="Duplicate operation name"):
        operation(
            OperationSpec[
                _DupInput,
                _DupOutput,
            ](
                name="diag.doctor",
                handler=_dup_async,
                sync_handler=_dup_sync,
                input_type=_DupInput,
                output_type=_DupOutput,
                cli_group="diag",
                cli_name="dup",
                mcp_name="diag_dup",
                description="duplicate",
            )
        )
