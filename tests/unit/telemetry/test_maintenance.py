from __future__ import annotations

import os
import time
from pathlib import Path

from meridian.lib.telemetry import maintenance


def test_cooldown_active_false_when_marker_missing(tmp_path: Path) -> None:
    assert not maintenance._cooldown_active(tmp_path / ".retention-marker", 3600)


def test_cooldown_active_true_when_marker_recent(tmp_path: Path) -> None:
    marker = tmp_path / ".retention-marker"
    marker.write_text("recent", encoding="utf-8")

    assert maintenance._cooldown_active(marker, 3600)


def test_cooldown_active_false_when_marker_old(tmp_path: Path) -> None:
    marker = tmp_path / ".retention-marker"
    marker.write_text("old", encoding="utf-8")
    old = time.time() - 7200
    os.utime(marker, (old, old))

    assert not maintenance._cooldown_active(marker, 3600)


def test_schedule_maintenance_creates_marker_when_cooldown_expired(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_root = tmp_path
    telemetry_dir = runtime_root / "telemetry"
    telemetry_dir.mkdir()
    marker = telemetry_dir / maintenance._MARKER_FILENAME

    calls: list[Path] = []

    def fake_cleanup(telemetry_path: Path, *, runtime_root: Path | None = None):
        calls.append(telemetry_path)
        return None

    monkeypatch.setattr(maintenance, "run_retention_cleanup", fake_cleanup)

    maintenance.schedule_maintenance(runtime_root, cooldown_seconds=0)

    deadline = time.time() + 2
    while time.time() < deadline and not marker.exists():
        time.sleep(0.01)

    assert marker.exists()
    assert calls == [telemetry_dir]


def test_schedule_maintenance_does_not_run_when_cooldown_active(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_root = tmp_path
    telemetry_dir = runtime_root / "telemetry"
    telemetry_dir.mkdir()
    marker = telemetry_dir / maintenance._MARKER_FILENAME
    marker.write_text("recent", encoding="utf-8")

    calls: list[Path] = []

    def fake_cleanup(telemetry_path: Path, *, runtime_root: Path | None = None):
        calls.append(telemetry_path)
        return None

    monkeypatch.setattr(maintenance, "run_retention_cleanup", fake_cleanup)

    maintenance.schedule_maintenance(runtime_root, cooldown_seconds=3600)
    time.sleep(0.05)

    assert calls == []
