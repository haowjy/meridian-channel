from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import pytest

telemetry_cmd = importlib.import_module("meridian.cli.telemetry_cmd")


def test_resolve_telemetry_dirs_global_collects_projects_and_legacy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_home = tmp_path / "user-home"
    first = user_home / "projects" / "alpha" / "telemetry"
    second = user_home / "projects" / "beta" / "telemetry"
    (user_home / "projects" / "gamma").mkdir(parents=True)
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    legacy = user_home / "telemetry"
    legacy.mkdir(parents=True)
    monkeypatch.setattr(telemetry_cmd, "get_user_home", lambda: user_home)

    assert telemetry_cmd._resolve_telemetry_dirs(True) == [first, second, legacy]


def test_resolve_telemetry_dirs_without_project_context_raises_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        telemetry_cmd,
        "resolve_project_root",
        lambda: (_ for _ in ()).throw(RuntimeError("no project")),
    )

    with pytest.raises(ValueError, match="Not inside a Meridian project"):
        telemetry_cmd._resolve_telemetry_dirs(False)


def test_telemetry_query_global_passes_all_dirs_and_filters(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    dirs = [Path("/tmp/project-a/telemetry"), Path("/tmp/project-b/telemetry")]
    captured: dict[str, Any] = {}

    def _fake_query_events(
        telemetry_dirs,
        *,
        since: str | None = None,
        domain: str | None = None,
        ids_filter: dict[str, str] | None = None,
        limit: int | None = None,
    ):
        captured.update(
            {
                "telemetry_dirs": telemetry_dirs,
                "since": since,
                "domain": domain,
                "ids_filter": ids_filter,
                "limit": limit,
            }
        )
        yield {"event": "chat.ws.connected"}

    monkeypatch.setattr(telemetry_cmd, "_resolve_telemetry_dirs", lambda global_flag: dirs)
    monkeypatch.setattr(telemetry_cmd, "query_events", _fake_query_events)

    telemetry_cmd._telemetry_query(
        since="1h",
        domain="chat",
        spawn_id="p1",
        chat_id="c1",
        work_id="w1",
        limit=10,
        global_flag=True,
    )

    assert captured == {
        "telemetry_dirs": dirs,
        "since": "1h",
        "domain": "chat",
        "ids_filter": {"spawn_id": "p1", "chat_id": "c1", "work_id": "w1"},
        "limit": 10,
    }
    assert json.loads(capsys.readouterr().out) == {"event": "chat.ws.connected"}


def test_telemetry_tail_global_passes_all_dirs_and_filters(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    dirs = [Path("/tmp/project-a/telemetry"), Path("/tmp/project-b/telemetry")]
    captured: dict[str, Any] = {}

    def _fake_tail_events(
        telemetry_dirs,
        *,
        domain: str | None = None,
        ids_filter: dict[str, str] | None = None,
    ):
        captured.update(
            {
                "telemetry_dirs": telemetry_dirs,
                "domain": domain,
                "ids_filter": ids_filter,
            }
        )
        yield {"event": "spawn.succeeded"}
        raise KeyboardInterrupt

    monkeypatch.setattr(telemetry_cmd, "_resolve_telemetry_dirs", lambda global_flag: dirs)
    monkeypatch.setattr(telemetry_cmd, "tail_events", _fake_tail_events)

    telemetry_cmd._telemetry_tail(
        domain="spawn",
        spawn_id="p2",
        chat_id="c2",
        work_id="w2",
        global_flag=True,
    )

    assert captured == {
        "telemetry_dirs": dirs,
        "domain": "spawn",
        "ids_filter": {"spawn_id": "p2", "chat_id": "c2", "work_id": "w2"},
    }
    assert json.loads(capsys.readouterr().out) == {"event": "spawn.succeeded"}


def test_telemetry_status_global_without_projects_emits_empty_status_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    emitted: list[dict[str, Any]] = []
    monkeypatch.setattr(telemetry_cmd, "_resolve_telemetry_dirs", lambda global_flag: [])

    telemetry_cmd._telemetry_status(emitted.append, global_flag=True)

    assert emitted == [
        {
            "segment_count": 0,
            "total_bytes": 0,
            "active_writers": [],
            "total_size_human": "0 B",
            "telemetry_dir": "",
            "rootless_note": telemetry_cmd.ROOTLESS_LIMITATION_NOTE,
        }
    ]
