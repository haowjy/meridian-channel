from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi import HTTPException

from meridian.lib.app import server as server_module
from meridian.lib.core.types import HarnessId, SpawnId
from meridian.lib.harness.connections.base import ConnectionCapabilities, ConnectionConfig
from meridian.lib.harness.launch_spec import ResolvedLaunchSpec
from meridian.lib.state.paths import resolve_runtime_paths
from meridian.lib.state.spawn_store import get_spawn
from meridian.lib.streaming.spawn_manager import DrainOutcome


class FakeConnection:
    harness_id = HarnessId.CODEX
    state = "connected"
    capabilities = ConnectionCapabilities(
        mid_turn_injection="queue",
        supports_steer=True,
        supports_cancel=True,
        runtime_model_switch=False,
        structured_reasoning=False,
    )


class FakeManager:
    def __init__(
        self,
        *,
        runtime_root: Path,
        project_root: Path,
        completion_ready: asyncio.Event,
        wait_calls: list[SpawnId],
        heartbeat_calls: list[SpawnId],
    ) -> None:
        self.runtime_root = runtime_root
        self.project_root = project_root
        self._completion_ready = completion_ready
        self._wait_calls = wait_calls
        self._heartbeat_calls = heartbeat_calls
        self.start_calls: list[tuple[ConnectionConfig, ResolvedLaunchSpec | None]] = []

    async def start_spawn(
        self,
        config: ConnectionConfig,
        spec: ResolvedLaunchSpec | None = None,
    ) -> FakeConnection:
        self.start_calls.append((config, spec))
        return FakeConnection()

    async def _start_heartbeat(self, spawn_id: SpawnId) -> None:
        self._heartbeat_calls.append(spawn_id)

    async def wait_for_completion(self, spawn_id: SpawnId) -> DrainOutcome | None:
        self._wait_calls.append(spawn_id)
        await self._completion_ready.wait()
        return DrainOutcome(status="succeeded", exit_code=0, duration_secs=2.5)

    async def shutdown(
        self,
        *,
        status: str = "cancelled",
        exit_code: int = 1,
        error: str | None = None,
    ) -> None:
        _ = status, exit_code, error

    def list_spawns(self) -> list[SpawnId]:
        return []

    def get_connection(self, spawn_id: SpawnId) -> object | None:
        _ = spawn_id
        return None


def _read_spawn_events(runtime_root: Path) -> list[dict[str, object]]:
    events_path = runtime_root / "spawns.jsonl"
    return [
        cast("dict[str, object]", json.loads(line))
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


async def _wait_until(predicate: Callable[[], bool], *, attempts: int = 200) -> None:
    for _ in range(attempts):
        if predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError("timed out waiting for condition")


def _create_spawn_handler(
    *,
    tmp_path: Path,
    completion_ready: asyncio.Event,
    wait_calls: list[SpawnId],
    heartbeat_calls: list[SpawnId],
    allow_unsafe_no_permissions: bool = False,
) -> tuple[Callable[[server_module.SpawnCreateRequest], Any], FakeManager]:
    manager = FakeManager(
        runtime_root=resolve_runtime_paths(tmp_path).root_dir,
        project_root=tmp_path,
        completion_ready=completion_ready,
        wait_calls=wait_calls,
        heartbeat_calls=heartbeat_calls,
    )

    app = server_module.create_app(
        cast("Any", manager),
        allow_unsafe_no_permissions=allow_unsafe_no_permissions,
    )

    for route in app.routes:
        if route.path == "/api/spawns" and "POST" in route.methods:
            endpoint = route.endpoint
            return cast("Callable[[server_module.SpawnCreateRequest], Any]", endpoint), manager
    raise AssertionError("missing /api/spawns POST route")


def _fake_launch_context(
    *,
    spawn_id: str,
    child_cwd: Path,
    prompt: str = "projected prompt",
    system: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        resolved_request=SimpleNamespace(
            model="gpt-5.4",
            harness="codex",
            agent="coder",
            prompt=prompt,
            skills=(),
            skill_paths=(),
            session=SimpleNamespace(requested_harness_session_id=None),
            agent_metadata={
                "appended_system_prompt": system,
                "session_agent_path": str(child_cwd / "agent.md"),
            },
        ),
        child_cwd=child_cwd,
        work_id="w123",
        env_overrides={
            "MERIDIAN_SPAWN_ID": spawn_id,
            "MERIDIAN_PARENT_SPAWN_ID": "p-parent",
            "EXTRA_ENV": "present",
        },
        spec=SimpleNamespace(name="fake-spec"),
    )


@pytest.mark.asyncio
async def test_app_server_create_spawn_background_finalizer_writes_finalize(
    tmp_path: Path,
) -> None:
    runtime_root = resolve_runtime_paths(tmp_path).root_dir
    completion_ready = asyncio.Event()
    wait_calls: list[SpawnId] = []
    heartbeat_calls: list[SpawnId] = []
    create_spawn_handler, _manager = _create_spawn_handler(
        tmp_path=tmp_path,
        completion_ready=completion_ready,
        wait_calls=wait_calls,
        heartbeat_calls=heartbeat_calls,
    )

    response = await create_spawn_handler(
        server_module.SpawnCreateRequest(
            harness="codex",
            prompt="hello",
            permissions=server_module.PermissionRequest(
                sandbox="workspace-write",
                approval="confirm",
            ),
        )
    )
    assert response["spawn_id"] == "p1"

    completion_ready.set()
    await _wait_until(lambda: len(_read_spawn_events(runtime_root)) == 3)

    events = _read_spawn_events(runtime_root)
    assert [event["event"] for event in events] == ["start", "update", "finalize"]
    assert events[-1]["status"] == "succeeded"
    assert events[-1]["exit_code"] == 0
    assert events[-1]["duration_secs"] == 2.5
    assert events[-1]["origin"] == "runner"
    assert wait_calls == [SpawnId("p1")]
    assert heartbeat_calls == [SpawnId("p1")]

    row = get_spawn(runtime_root, "p1")
    assert row is not None
    assert row.status == "succeeded"
    assert row.exit_code == 0
    assert row.duration_secs == 2.5
    assert row.launch_mode == "app"
    assert row.runner_pid == os.getpid()


@pytest.mark.asyncio
async def test_app_server_permission_policy_gate(tmp_path: Path) -> None:
    rejected_handler, _ = _create_spawn_handler(
        tmp_path=tmp_path,
        completion_ready=asyncio.Event(),
        wait_calls=[],
        heartbeat_calls=[],
    )

    with pytest.raises(HTTPException) as exc_info:
        await rejected_handler(
            server_module.SpawnCreateRequest(
                harness="codex",
                prompt="hello",
            )
        )
    assert exc_info.value.status_code == 400
    assert "permissions block is required" in str(exc_info.value.detail)

    allowed_completion_ready = asyncio.Event()
    allowed_wait_calls: list[SpawnId] = []
    allowed_heartbeat_calls: list[SpawnId] = []
    allowed_handler, _manager = _create_spawn_handler(
        tmp_path=tmp_path / "unsafe",
        completion_ready=allowed_completion_ready,
        wait_calls=allowed_wait_calls,
        heartbeat_calls=allowed_heartbeat_calls,
        allow_unsafe_no_permissions=True,
    )

    response = await allowed_handler(
        server_module.SpawnCreateRequest(
            harness="codex",
            prompt="hello",
        )
    )
    assert response["spawn_id"] == "p1"

    allowed_completion_ready.set()
    await _wait_until(lambda: allowed_wait_calls == [SpawnId("p1")])
    assert allowed_heartbeat_calls == [SpawnId("p1")]


@pytest.mark.asyncio
async def test_app_server_composition_failure_leaves_no_spawn_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = resolve_runtime_paths(tmp_path).root_dir

    def _raising_build_launch_context(**kwargs: object) -> object:
        _ = kwargs
        raise ValueError("compose failed")

    monkeypatch.setattr(
        "meridian.lib.core.spawn_service.build_launch_context",
        _raising_build_launch_context,
    )
    create_spawn_handler, _manager = _create_spawn_handler(
        tmp_path=tmp_path,
        completion_ready=asyncio.Event(),
        wait_calls=[],
        heartbeat_calls=[],
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_spawn_handler(
            server_module.SpawnCreateRequest(
                harness="codex",
                prompt="hello",
                permissions=server_module.PermissionRequest(
                    sandbox="workspace-write",
                    approval="confirm",
                ),
            )
        )

    assert exc_info.value.status_code == 400
    assert str(exc_info.value.detail) == "compose failed"
    assert get_spawn(runtime_root, "p1") is None
    assert not (runtime_root / "spawns.jsonl").exists()


@pytest.mark.asyncio
async def test_app_server_create_spawn_projects_connection_config_from_launch_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = resolve_runtime_paths(tmp_path).root_dir
    child_cwd = tmp_path / "child-cwd"
    child_cwd.mkdir()
    completion_ready = asyncio.Event()
    wait_calls: list[SpawnId] = []
    heartbeat_calls: list[SpawnId] = []

    def _build_launch_context(**kwargs: object) -> SimpleNamespace:
        return _fake_launch_context(
            spawn_id=str(kwargs["spawn_id"]),
            child_cwd=child_cwd,
            system="SYSTEM: projected",
        )

    monkeypatch.setattr(
        "meridian.lib.core.spawn_service.build_launch_context",
        _build_launch_context,
    )
    create_spawn_handler, manager = _create_spawn_handler(
        tmp_path=tmp_path,
        completion_ready=completion_ready,
        wait_calls=wait_calls,
        heartbeat_calls=heartbeat_calls,
    )

    response = await create_spawn_handler(
        server_module.SpawnCreateRequest(
            harness="codex",
            prompt="hello",
            permissions=server_module.PermissionRequest(
                sandbox="workspace-write",
                approval="confirm",
            ),
        )
    )

    assert response["spawn_id"] == "p1"
    assert len(manager.start_calls) == 1
    config, spec = manager.start_calls[0]
    assert config.spawn_id == SpawnId("p1")
    assert config.prompt == "projected prompt"
    assert config.project_root == child_cwd
    assert config.system == "SYSTEM: projected"
    assert config.env_overrides["MERIDIAN_SPAWN_ID"] == "p1"
    assert config.env_overrides["MERIDIAN_PARENT_SPAWN_ID"] == "p-parent"
    assert config.env_overrides["EXTRA_ENV"] == "present"
    assert spec.name == "fake-spec"

    completion_ready.set()
    await _wait_until(lambda: len(_read_spawn_events(runtime_root)) == 3)

    row = get_spawn(runtime_root, "p1")
    assert row is not None
    assert row.execution_cwd == str(child_cwd)
    assert row.work_id == "w123"


@pytest.mark.asyncio
async def test_app_server_start_spawn_failure_tags_launch_failure_origin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = resolve_runtime_paths(tmp_path).root_dir

    async def _raising_start_spawn(
        self: FakeManager,
        config: ConnectionConfig,
        spec: ResolvedLaunchSpec | None = None,
    ) -> FakeConnection:
        _ = self, config, spec
        raise RuntimeError("start failed")

    monkeypatch.setattr(FakeManager, "start_spawn", _raising_start_spawn)
    create_spawn_handler, _manager = _create_spawn_handler(
        tmp_path=tmp_path,
        completion_ready=asyncio.Event(),
        wait_calls=[],
        heartbeat_calls=[],
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_spawn_handler(
            server_module.SpawnCreateRequest(
                harness="codex",
                prompt="hello",
                permissions=server_module.PermissionRequest(
                    sandbox="workspace-write",
                    approval="confirm",
                ),
            )
        )

    assert exc_info.value.status_code == 400
    assert str(exc_info.value.detail) == "start failed"
    events = _read_spawn_events(runtime_root)
    assert [event["event"] for event in events] == ["start", "update", "finalize"]
    assert events[-1]["status"] == "failed"
    assert events[-1]["origin"] == "launch_failure"
    assert events[-2]["status"] == "finalizing"
