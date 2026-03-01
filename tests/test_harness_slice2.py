"""Slice 2 harness and direct-tool-definition tests."""

from __future__ import annotations

import typing

from meridian.lib.harness.direct import DirectAdapter, _normalize_optional
from meridian.lib.harness.registry import HarnessRegistry
from meridian.lib.ops.registry import get_all_operations


def test_harness_registry_has_all_builtins() -> None:
    registry = HarnessRegistry.with_defaults()
    assert set(registry.ids()) == {"claude", "codex", "opencode", "direct"}


def test_direct_adapter_tool_definitions_include_allowed_callers() -> None:
    tools = DirectAdapter.build_tool_definitions()
    assert tools[0]["name"] == "code_execution"
    assert tools[0]["type"] == "code_execution_20260120"

    by_name = {str(tool.get("name")): tool for tool in tools}
    for operation in get_all_operations():
        if operation.cli_only:
            continue
        assert operation.mcp_name in by_name
        tool = by_name[operation.mcp_name]
        assert tool["allowed_callers"] == ["code_execution_20260120"]
        assert isinstance(tool["input_schema"], dict)

    assert "skills_search" in by_name
    assert "models_show" in by_name


def test_normalize_optional_supports_union_forms() -> None:
    normalized_pipe, pipe_is_optional = _normalize_optional(str | None)
    assert normalized_pipe is str
    assert pipe_is_optional is True

    normalized_union, union_is_optional = _normalize_optional(
        typing.__dict__["Union"][int, None],
    )
    assert normalized_union is int
    assert union_is_optional is True
