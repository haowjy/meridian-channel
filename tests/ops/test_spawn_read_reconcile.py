import os
from pathlib import Path

import meridian.lib.ops.spawn.api as spawn_api
from meridian.lib.ops.spawn.models import SpawnListInput, SpawnShowInput
from meridian.lib.state import spawn_store
from meridian.lib.state.paths import resolve_state_paths


def _state_root(repo_root: Path) -> Path:
    state_root = resolve_state_paths(repo_root).root_dir
    state_root.mkdir(parents=True, exist_ok=True)
    return state_root


def _seed_running_spawn(state_root: Path, spawn_id: str) -> None:
    spawn_store.start_spawn(
        state_root,
        spawn_id=spawn_id,
        chat_id="c1",
        model="gpt-5.3-codex",
        agent="coder",
        harness="codex",
        prompt="hello",
        runner_pid=os.getpid(),
    )


def test_spawn_show_sync_renders_running_post_exit_finalization_state(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    state_root = _state_root(repo_root)
    _seed_running_spawn(state_root, "p1")
    spawn_store.record_spawn_exited(
        state_root,
        "p1",
        exit_code=143,
        exited_at="2026-04-12T14:00:00Z",
    )

    output = spawn_api.spawn_show_sync(
        SpawnShowInput(
            spawn_id="p1",
            include_report_body=False,
            repo_root=repo_root.as_posix(),
        )
    )

    assert output.spawn_id == "p1"
    assert output.status == "running"
    assert output.exited_at == "2026-04-12T14:00:00Z"
    assert output.process_exit_code == 143
    assert "running (exited 143, awaiting finalization)" in output.format_text()


def test_spawn_list_sync_marks_running_post_exit_with_asterisk(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    state_root = _state_root(repo_root)
    _seed_running_spawn(state_root, "p2")
    spawn_store.record_spawn_exited(
        state_root,
        "p2",
        exit_code=0,
        exited_at="2026-04-12T14:00:00Z",
    )

    output = spawn_api.spawn_list_sync(SpawnListInput(repo_root=repo_root.as_posix()))

    assert len(output.spawns) == 1
    assert output.spawns[0].status == "running"
    assert output.spawns[0].status_display == "running*"
    assert "running*" in output.format_text()
