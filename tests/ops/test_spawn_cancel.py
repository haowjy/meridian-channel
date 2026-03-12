from pathlib import Path

from meridian.lib.ops.spawn.api import spawn_cancel_sync
from meridian.lib.ops.spawn.models import SpawnCancelInput
from meridian.lib.state import spawn_store
from meridian.lib.state.paths import resolve_state_paths


_OLD_STARTED_AT = "2000-01-01T00:00:00Z"


def _start_running_spawn(tmp_path: Path, *, started_at: str | None = None) -> tuple[Path, str]:
    state_root = resolve_state_paths(tmp_path).root_dir
    spawn_id = spawn_store.start_spawn(
        state_root,
        chat_id="c1",
        model="gpt-5.4",
        agent="agent",
        harness="codex",
        kind="child",
        prompt="hello",
        launch_mode="background",
        status="queued",
        started_at=started_at,
    )
    return state_root, str(spawn_id)


def test_spawn_cancel_finalizes_running_spawn_without_background_pid(tmp_path: Path) -> None:
    state_root, spawn_id = _start_running_spawn(tmp_path, started_at=_OLD_STARTED_AT)

    result = spawn_cancel_sync(SpawnCancelInput(spawn_id=spawn_id, repo_root=tmp_path.as_posix()))

    assert result.status == "cancelled"
    latest = spawn_store.get_spawn(state_root, spawn_id)
    assert latest is not None
    assert latest.status == "cancelled"
    assert latest.exit_code == 130
    assert latest.error == "cancelled"
