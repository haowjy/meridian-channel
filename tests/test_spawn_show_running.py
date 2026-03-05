"""spawn.show running-state detail fields."""

from __future__ import annotations

import json
from pathlib import Path

from meridian.lib.ops.spawn import SpawnShowInput, spawn_show_sync
from meridian.lib.space.space_file import create_space
from meridian.lib.state import spawn_store
from meridian.lib.state.paths import resolve_space_dir


def _start_running_spawn(space_dir: Path) -> str:
    return str(
        spawn_store.start_spawn(
            space_dir,
            chat_id="c1",
            model="gpt-5.3-codex",
            agent="coder",
            harness="codex",
            prompt="working",
        )
    )


def test_spawn_show_running_includes_log_path_last_message_and_tail_hint(tmp_path: Path) -> None:
    space = create_space(tmp_path, name="show-running")
    space_dir = resolve_space_dir(tmp_path, space.id)
    spawn_id = _start_running_spawn(space_dir)

    log_path = space_dir / "spawns" / spawn_id / "stderr.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    long_assistant_text = "assistant " + ("message " * 30)
    log_path.write_text(
        "\n".join(
            [
                "plain startup line",
                json.dumps({"type": "assistant", "text": "first"}),
                json.dumps({"type": "assistant", "text": long_assistant_text}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    detail = spawn_show_sync(
        SpawnShowInput(spawn_id=spawn_id, space=space.id, repo_root=tmp_path.as_posix())
    )

    assert detail.status == "running"
    assert detail.log_path == log_path.as_posix()
    assert detail.last_message is not None
    assert len(detail.last_message) <= 120
    assert detail.last_message.endswith("...")
    rendered = detail.format_text()
    assert f"Log: {log_path.as_posix()}" in rendered
    assert f"Hint: tail -f {log_path.as_posix()}" in rendered


def test_spawn_show_non_running_omits_running_log_fields(tmp_path: Path) -> None:
    space = create_space(tmp_path, name="show-finished")
    space_dir = resolve_space_dir(tmp_path, space.id)
    spawn_id = _start_running_spawn(space_dir)
    spawn_store.finalize_spawn(space_dir, spawn_id, status="succeeded", exit_code=0)

    detail = spawn_show_sync(
        SpawnShowInput(spawn_id=spawn_id, space=space.id, repo_root=tmp_path.as_posix())
    )

    assert detail.status == "succeeded"
    assert detail.last_message is None
    assert detail.log_path is None
