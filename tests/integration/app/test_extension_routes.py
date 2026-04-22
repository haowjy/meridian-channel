"""Integration tests for extension HTTP routes."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from meridian.lib.app.server import create_app
from meridian.lib.core.types import SpawnId
from meridian.lib.extensions.registry import (
    build_first_party_registry,
    compute_manifest_hash,
)
from meridian.lib.state.paths import resolve_runtime_paths


class FakeManager:
    def __init__(self, *, project_root: Path) -> None:
        self.project_root = project_root
        self.runtime_root = resolve_runtime_paths(project_root).root_dir

    async def shutdown(self) -> None:
        return None

    def list_spawns(self) -> list[SpawnId]:
        return []

    def get_connection(self, spawn_id: SpawnId) -> object | None:
        _ = spawn_id
        return None


@pytest.fixture
def app_client(tmp_path: Path) -> Iterator[TestClient]:
    manager = FakeManager(project_root=tmp_path)
    app = create_app(cast("Any", manager), allow_unsafe_no_permissions=True)
    with TestClient(app) as client:
        yield client


class TestDiscoveryRoutes:
    """EB2.1, EB2.2: Discovery routes work without auth."""

    def test_list_extensions_no_auth_required(self, app_client: TestClient) -> None:
        """GET /api/extensions requires no auth."""
        response = app_client.get("/api/extensions")
        assert response.status_code == 200
        data = response.json()
        assert "schema_version" in data
        assert "manifest_hash" in data
        assert "extensions" in data

    def test_manifest_hash_route_no_auth(self, app_client: TestClient) -> None:
        """GET /api/extensions/manifest-hash requires no auth."""
        response = app_client.get("/api/extensions/manifest-hash")
        assert response.status_code == 200
        data = response.json()
        assert "manifest_hash" in data

    def test_extension_commands_list(self, app_client: TestClient) -> None:
        """GET /api/extensions/{ext}/commands returns commands."""
        response = app_client.get("/api/extensions/meridian.sessions/commands")
        assert response.status_code == 200
        data = response.json()
        assert "commands" in data
        command_ids = [command["command_id"] for command in data["commands"]]
        assert "archiveSpawn" in command_ids
        assert "getSpawnStats" in command_ids


class TestRouteShadowing:
    """EB2.9: Static routes not shadowed by dynamic."""

    def test_manifest_hash_not_shadowed(self, app_client: TestClient) -> None:
        """manifest-hash is not captured by /{extension_id}."""
        response = app_client.get("/api/extensions/manifest-hash")
        assert response.status_code == 200
        data = response.json()
        assert "manifest_hash" in data
        assert "commands" not in data

    def test_operations_stub_not_shadowed(self, app_client: TestClient) -> None:
        """operations/{id} is not captured by /{extension_id}."""
        response = app_client.get("/api/extensions/operations/some-op-id")
        assert response.status_code == 404
        data = response.json()
        message = str(data.get("message", ""))
        assert "not yet implemented" in message.lower() or "Operations" in message


class TestManifestHashParity:
    """EB1.12 via HTTP: HTTP hash matches in-process hash."""

    def test_http_hash_matches_in_process(self, app_client: TestClient) -> None:
        registry = build_first_party_registry()
        in_process_hash = compute_manifest_hash(registry)[:16]

        response = app_client.get("/api/extensions/manifest-hash")
        http_hash = response.json()["manifest_hash"]

        assert http_hash == in_process_hash


class TestInvokeAuth:
    """EB2.3, EB2.4: Invoke requires auth."""

    def test_invoke_without_token_returns_401(self, app_client: TestClient) -> None:
        """Missing Authorization header returns 401."""
        response = app_client.post(
            "/api/extensions/meridian.workbench/commands/ping/invoke",
            json={"args": {}},
        )
        assert response.status_code == 401

    def test_invoke_with_wrong_token_returns_401(self, app_client: TestClient) -> None:
        """Wrong Bearer token returns 401."""
        response = app_client.post(
            "/api/extensions/meridian.workbench/commands/ping/invoke",
            json={"args": {}},
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert response.status_code == 401
