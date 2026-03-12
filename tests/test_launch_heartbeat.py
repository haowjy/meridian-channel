from __future__ import annotations
# pyright: reportPrivateUsage=false

import asyncio
import time
from pathlib import Path

import pytest

from meridian.lib.launch import heartbeat as heartbeat_module
from meridian.lib.launch.heartbeat import (
    _touch_heartbeat,
    heartbeat_scope,
    threaded_heartbeat_scope,
)
from meridian.lib.state.reaper_config import validate_stale_threshold_secs


def _read_heartbeat_timestamp(path: Path) -> float:
    return float(path.read_text(encoding="utf-8").strip())


def test_touch_heartbeat_creates_file(tmp_path: Path) -> None:
    heartbeat_path = tmp_path / "heartbeats" / "heartbeat.txt"

    _touch_heartbeat(heartbeat_path)

    assert heartbeat_path.is_file()
    assert isinstance(_read_heartbeat_timestamp(heartbeat_path), float)


@pytest.mark.asyncio
async def test_heartbeat_scope_writes_and_cancels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    heartbeat_path = tmp_path / "heartbeat.txt"

    created_task: asyncio.Task[None] | None = None
    real_create_task = heartbeat_module.asyncio.create_task

    def _recording_create_task(coro: object) -> asyncio.Task[None]:
        nonlocal created_task
        created_task = real_create_task(coro)  # type: ignore[arg-type]
        return created_task

    monkeypatch.setattr(heartbeat_module.asyncio, "create_task", _recording_create_task)

    async with heartbeat_scope(heartbeat_path, interval_secs=0.1):
        await asyncio.sleep(0.03)
        assert heartbeat_path.is_file()
        assert time.time() - heartbeat_path.stat().st_mtime < 1.0

    assert heartbeat_path.is_file()
    assert created_task is not None
    assert created_task.done()
    assert created_task.cancelled()


@pytest.mark.asyncio
async def test_heartbeat_scope_interval(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    heartbeat_path = tmp_path / "heartbeat.txt"

    touches: list[float] = []
    real_touch = heartbeat_module._touch_heartbeat

    def _recording_touch(path: Path) -> None:
        real_touch(path)
        touches.append(_read_heartbeat_timestamp(path))

    monkeypatch.setattr(heartbeat_module, "_touch_heartbeat", _recording_touch)

    async with heartbeat_scope(heartbeat_path, interval_secs=0.05):
        await asyncio.sleep(0.16)

    assert len(touches) >= 2
    assert touches[-1] > touches[0]


def test_threaded_heartbeat_scope_writes_and_stops(tmp_path: Path) -> None:
    heartbeat_path = tmp_path / "heartbeat.txt"

    start = time.monotonic()
    with threaded_heartbeat_scope(heartbeat_path, interval_secs=1.0):
        while not heartbeat_path.exists() and time.monotonic() - start < 0.2:
            time.sleep(0.01)
        assert heartbeat_path.is_file()
        first_mtime = heartbeat_path.stat().st_mtime

    assert heartbeat_path.is_file()
    time.sleep(1.1)
    assert heartbeat_path.stat().st_mtime == first_mtime


def test_threaded_heartbeat_scope_interval(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    heartbeat_path = tmp_path / "heartbeat.txt"

    touches: list[float] = []
    real_touch = heartbeat_module._touch_heartbeat

    def _recording_touch(path: Path) -> None:
        real_touch(path)
        touches.append(_read_heartbeat_timestamp(path))

    monkeypatch.setattr(heartbeat_module, "_touch_heartbeat", _recording_touch)

    with threaded_heartbeat_scope(heartbeat_path, interval_secs=0.05):
        time.sleep(0.18)

    assert len(touches) >= 2
    assert touches[-1] > touches[0]


def test_validate_stale_threshold_valid() -> None:
    assert validate_stale_threshold_secs(60) == 60
    assert validate_stale_threshold_secs(86_400) == 86_400
    assert validate_stale_threshold_secs(300) == 300


def test_validate_stale_threshold_too_low() -> None:
    with pytest.raises(ValueError):
        validate_stale_threshold_secs(59)


def test_validate_stale_threshold_too_high() -> None:
    with pytest.raises(ValueError):
        validate_stale_threshold_secs(86_401)


def test_validate_stale_threshold_coerces_string() -> None:
    assert validate_stale_threshold_secs("300") == 300
