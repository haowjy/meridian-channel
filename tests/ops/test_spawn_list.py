from pathlib import Path

from meridian.lib.ops.spawn.api import spawn_list_sync
from meridian.lib.ops.spawn.models import SpawnListInput
from meridian.lib.state import spawn_store
from meridian.lib.state.paths import resolve_state_paths


def test_spawn_list_defaults_to_active_view(tmp_path: Path) -> None:
    state_root = resolve_state_paths(tmp_path).root_dir
    running_id = spawn_store.start_spawn(
        state_root,
        chat_id="c1",
        model="gpt-5.4",
        agent="agent",
        harness="codex",
        kind="child",
        prompt="running",
    )
    succeeded_id = spawn_store.start_spawn(
        state_root,
        chat_id="c1",
        model="gpt-5.4",
        agent="agent",
        harness="codex",
        kind="child",
        prompt="done",
    )
    spawn_store.finalize_spawn(state_root, succeeded_id, status="succeeded", exit_code=0)

    result = spawn_list_sync(SpawnListInput(repo_root=tmp_path.as_posix()))

    assert tuple(entry.spawn_id for entry in result.spawns) == (str(running_id),)


def test_spawn_list_statuses_empty_tuple_means_all_rows(tmp_path: Path) -> None:
    state_root = resolve_state_paths(tmp_path).root_dir
    running_id = spawn_store.start_spawn(
        state_root,
        chat_id="c1",
        model="gpt-5.4",
        agent="agent",
        harness="codex",
        kind="child",
        prompt="running",
    )
    failed_id = spawn_store.start_spawn(
        state_root,
        chat_id="c1",
        model="gpt-5.4",
        agent="agent",
        harness="codex",
        kind="child",
        prompt="failed",
    )
    spawn_store.finalize_spawn(state_root, failed_id, status="failed", exit_code=1)

    result = spawn_list_sync(SpawnListInput(repo_root=tmp_path.as_posix(), statuses=()))

    assert {entry.spawn_id for entry in result.spawns} == {str(running_id), str(failed_id)}
