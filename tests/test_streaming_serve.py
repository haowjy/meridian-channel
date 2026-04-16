from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from meridian.cli import streaming_serve as streaming_serve_module
from meridian.lib.state.paths import resolve_state_paths
from meridian.lib.state.spawn_store import finalize_spawn, get_spawn


def _read_spawn_events(state_root: Path) -> list[dict[str, object]]:
    events_path = state_root / "spawns.jsonl"
    return [
        cast("dict[str, object]", json.loads(line))
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.mark.asyncio
async def test_streaming_serve_shutdown_finalizes_once_as_cancelled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path
    state_root = resolve_state_paths(repo_root).root_dir
    helper_calls: list[tuple[str, str]] = []

    async def _execute_with_streaming(**kwargs: object) -> int:
        spawn_id = str(kwargs["run"].spawn_id)
        helper_calls.append((spawn_id, str(kwargs["state_root"])))
        finalize_spawn(
            state_root,
            spawn_id,
            status="cancelled",
            exit_code=1,
            origin="runner",
        )
        return 1

    monkeypatch.setattr(streaming_serve_module, "execute_with_streaming", _execute_with_streaming)
    monkeypatch.setattr(
        streaming_serve_module,
        "resolve_runtime_root_and_config",
        lambda repo_root=None, *, sink=None: (repo_root or tmp_path, None),
    )

    await streaming_serve_module.streaming_serve("codex", "hello")

    assert helper_calls == [("p1", str(state_root))]
    events = _read_spawn_events(state_root)
    assert [event["event"] for event in events] == ["start", "finalize"]
    assert events[-1]["status"] == "cancelled"

    row = get_spawn(state_root, "p1")
    assert row is not None
    assert row.status == "cancelled"
    assert row.exit_code == 1


@pytest.mark.asyncio
async def test_streaming_serve_start_failure_finalizes_failed_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path
    state_root = resolve_state_paths(repo_root).root_dir

    async def _execute_with_streaming(**kwargs: object) -> int:
        _ = kwargs
        raise RuntimeError("boom")

    monkeypatch.setattr(streaming_serve_module, "execute_with_streaming", _execute_with_streaming)
    monkeypatch.setattr(
        streaming_serve_module,
        "resolve_runtime_root_and_config",
        lambda repo_root=None, *, sink=None: (repo_root or tmp_path, None),
    )

    with pytest.raises(RuntimeError, match="boom"):
        await streaming_serve_module.streaming_serve("codex", "hello")

    events = _read_spawn_events(state_root)
    assert [event["event"] for event in events] == ["start", "finalize"]
    assert events[-1]["status"] == "failed"
    assert events[-1]["error"] == "boom"

    row = get_spawn(state_root, "p1")
    assert row is not None
    assert row.status == "failed"
    assert row.error == "boom"
