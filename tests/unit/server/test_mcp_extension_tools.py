"""Unit tests for MCP extension tools."""

from __future__ import annotations

from pathlib import Path

import pytest

import meridian.server.main as server_main
from meridian.lib.extensions.registry import build_first_party_registry
from meridian.server.main import extension_invoke, extension_list_commands


class TestExtensionListCommands:
    """Tests for extension_list_commands MCP tool."""

    @pytest.mark.asyncio
    async def test_returns_same_fqids_as_cli(self) -> None:
        """EB3.8: Same fqids as CLI discovery."""
        mcp_result = await extension_list_commands()
        mcp_fqids = {command["fqid"] for command in mcp_result["commands"]}

        registry = build_first_party_registry()
        cli_fqids = {spec.fqid for spec in registry.list_all()}

        assert mcp_fqids == cli_fqids


class TestExtensionInvoke:
    """Tests for extension_invoke MCP tool."""

    @pytest.mark.asyncio
    async def test_not_found_returns_structured_error(self) -> None:
        """EB3.11: Structured error for not found."""
        result = await extension_invoke(fqid="nonexistent.command", args={})
        assert result["status"] == "error"
        assert result["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_no_app_server_returns_structured_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """EB3.11: Structured error when app server required but not running."""

        def _fake_resolve_runtime_root_and_config_for_read(
            _project_root: str | None,
        ) -> tuple[Path, object]:
            return tmp_path / "project", object()

        def _fake_resolve_runtime_root_for_read(_project_root: Path) -> Path:
            return tmp_path / "runtime"

        monkeypatch.setattr(
            server_main,
            "resolve_runtime_root_and_config_for_read",
            _fake_resolve_runtime_root_and_config_for_read,
        )
        monkeypatch.setattr(
            server_main,
            "resolve_runtime_root_for_read",
            _fake_resolve_runtime_root_for_read,
        )
        monkeypatch.setattr(server_main, "get_project_uuid", lambda _project_root: "project-uuid")

        result = await extension_invoke(
            fqid="meridian.sessions.getSpawnStats",
            args={"spawn_id": "p123"},
        )
        assert result["status"] == "error"
        assert result["code"] == "app_server_required"
