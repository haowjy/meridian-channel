"""Unit tests for first-party extension command handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from meridian.lib.extensions.commands.sessions import (
    archive_spawn_handler,
    get_spawn_stats_handler,
)
from meridian.lib.extensions.commands.workbench import ping_handler
from meridian.lib.extensions.context import (
    ExtensionCommandServices,
    ExtensionInvocationContext,
    ExtensionInvocationContextBuilder,
)
from meridian.lib.extensions.registry import build_first_party_registry
from meridian.lib.extensions.types import (
    ExtensionErrorResult,
    ExtensionJSONResult,
    ExtensionSurface,
)
from meridian.lib.ops.spawn.models import SpawnStatsInput, SpawnStatsOutput


def _build_context() -> ExtensionInvocationContext:
    return (
        ExtensionInvocationContextBuilder(ExtensionSurface.HTTP)
        .with_project_uuid("project-uuid")
        .build()
    )


def test_first_party_registry_contains_wrapped_operations() -> None:
    registry = build_first_party_registry()
    all_fqids = {spec.fqid for spec in registry.list_all()}
    v1_fqids = {
        "meridian.sessions.archiveSpawn",
        "meridian.sessions.getSpawnStats",
        "meridian.workbench.ping",
    }

    # Original v1 commands are preserved.
    assert v1_fqids.issubset(all_fqids)

    # Wrapped operations are registered (39 operations + 3 v1 = 42).
    assert len(registry) >= 42
    assert len(all_fqids - v1_fqids) >= 39

    # Spot-check wrapped operation fqids.
    assert "meridian.spawn.create" in all_fqids
    assert "meridian.config.show" in all_fqids
    assert "meridian.work.list" in all_fqids


@pytest.mark.asyncio
async def test_ping_handler_returns_ok_true() -> None:
    result = await ping_handler({}, _build_context(), ExtensionCommandServices())

    assert isinstance(result, ExtensionJSONResult)
    assert result.payload == {"ok": True}


@pytest.mark.asyncio
async def test_archive_spawn_handler_uses_spawn_archive_helper(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import meridian.lib.spawn.archive as archive_mod

    calls: list[tuple[Path, str]] = []

    def _fake_is_archived(runtime_root: Path, spawn_id: str) -> bool:
        _ = (runtime_root, spawn_id)
        return False

    def _fake_archive(runtime_root: Path, spawn_id: str) -> None:
        calls.append((runtime_root, spawn_id))

    monkeypatch.setattr(archive_mod, "is_spawn_archived", _fake_is_archived)
    monkeypatch.setattr(archive_mod, "archive_spawn", _fake_archive)

    result = await archive_spawn_handler(
        {"spawn_id": "p123"},
        _build_context(),
        ExtensionCommandServices(runtime_root=tmp_path),
    )

    assert isinstance(result, ExtensionJSONResult)
    assert result.payload == {"spawn_id": "p123", "archived": True}
    assert calls == [(tmp_path, "p123")]


@pytest.mark.asyncio
async def test_get_spawn_stats_returns_spawn_stats_output_compatible_data(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import meridian.lib.ops.spawn.api as spawn_api_mod

    captured: dict[str, Any] = {}
    expected = SpawnStatsOutput(
        total_runs=2,
        succeeded=1,
        failed=1,
        cancelled=0,
        running=0,
        finalizing=0,
        total_duration_secs=9.5,
        total_cost_usd=0.1234,
        models={},
        children=(),
    )

    def _fake_spawn_stats_sync(payload: object) -> SpawnStatsOutput:
        captured["payload"] = payload
        return expected

    monkeypatch.setattr(spawn_api_mod, "spawn_stats_sync", _fake_spawn_stats_sync)

    meridian_dir = tmp_path / ".meridian"
    result = await get_spawn_stats_handler(
        {"spawn_id": "p42"},
        _build_context(),
        ExtensionCommandServices(meridian_dir=meridian_dir),
    )

    if isinstance(result, ExtensionErrorResult):
        pytest.fail(f"unexpected error result: {result}")
    assert isinstance(result, ExtensionJSONResult)

    payload = captured["payload"]
    assert isinstance(payload, SpawnStatsInput)
    assert payload.spawn_id == "p42"
    assert payload.project_root == tmp_path.as_posix()
    parsed = SpawnStatsOutput.model_validate(result.payload)
    assert parsed == expected
