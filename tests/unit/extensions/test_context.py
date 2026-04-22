"""Unit tests for extension invocation context and capabilities."""

from __future__ import annotations

from pathlib import Path

from meridian.lib.extensions.context import (
    ExtensionCapabilities,
    ExtensionInvocationContextBuilder,
)
from meridian.lib.extensions.types import ExtensionSurface


def test_cli_surface_defaults_to_denied_capabilities() -> None:
    context = ExtensionInvocationContextBuilder(ExtensionSurface.CLI).build()

    assert context.capabilities == ExtensionCapabilities.denied()
    assert not context.capabilities.subprocess
    assert not context.capabilities.kernel
    assert not context.capabilities.hitl


def test_mcp_surface_defaults_to_denied_capabilities() -> None:
    context = ExtensionInvocationContextBuilder(ExtensionSurface.MCP).build()

    assert context.capabilities == ExtensionCapabilities.denied()


def test_http_surface_defaults_to_elevated_capabilities() -> None:
    context = ExtensionInvocationContextBuilder(ExtensionSurface.HTTP).build()

    assert context.capabilities == ExtensionCapabilities.elevated()
    assert context.capabilities.has("subprocess")
    assert context.capabilities.has("kernel")
    assert context.capabilities.has("hitl")


def test_explicit_capabilities_override_surface_defaults() -> None:
    explicit_caps = ExtensionCapabilities(subprocess=True, kernel=False, hitl=False)

    context = (
        ExtensionInvocationContextBuilder(ExtensionSurface.CLI)
        .with_capabilities(explicit_caps)
        .build()
    )

    assert context.capabilities == explicit_caps
    assert context.capabilities.subprocess
    assert not context.capabilities.kernel
    assert not context.capabilities.hitl


def test_work_path_resolves_only_when_work_exists(tmp_path: Path) -> None:
    existing_work_path = tmp_path / "work-existing"
    existing_work_path.mkdir()
    missing_work_path = tmp_path / "work-missing"

    existing_context = (
        ExtensionInvocationContextBuilder(ExtensionSurface.HTTP)
        .with_work_id("work-existing")
        .with_work_path(existing_work_path)
        .build()
    )
    missing_context = (
        ExtensionInvocationContextBuilder(ExtensionSurface.HTTP)
        .with_work_id("work-missing")
        .with_work_path(missing_work_path)
        .build()
    )

    assert existing_context.work_path == existing_work_path
    assert missing_context.work_path is None


def test_builder_supports_fluent_interface(tmp_path: Path) -> None:
    work_path = tmp_path / "work-123"
    work_path.mkdir()
    explicit_caps = ExtensionCapabilities(subprocess=True, kernel=False, hitl=True)

    context = (
        ExtensionInvocationContextBuilder(ExtensionSurface.HTTP)
        .with_project_uuid("project-uuid")
        .with_work_id("work-123")
        .with_work_path(work_path)
        .with_capabilities(explicit_caps)
        .with_request_id("request-abc")
        .build()
    )

    assert context.caller_surface is ExtensionSurface.HTTP
    assert context.project_uuid == "project-uuid"
    assert context.work_id == "work-123"
    assert context.work_path == work_path
    assert context.capabilities == explicit_caps
    assert context.request_id == "request-abc"
