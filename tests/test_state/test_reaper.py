import os
import subprocess
from pathlib import Path

from meridian.lib.state import spawn_store
from meridian.lib.state.paths import resolve_state_paths
from meridian.lib.state.reaper import reconcile_active_spawn
from meridian.lib.core.domain import SpawnStatus


_OLD_STARTED_AT = "2000-01-01T00:00:00Z"


def _start_background_spawn(
    tmp_path: Path,
    *,
    started_at: str | None = None,
    status: SpawnStatus = "queued",
) -> tuple[Path, str]:
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
        status=status,
        started_at=started_at,
    )
    return state_root, str(spawn_id)


def test_reconcile_active_spawn_marks_missing_spawn_dir_failed_after_grace(tmp_path: Path) -> None:
    state_root, spawn_id = _start_background_spawn(tmp_path, started_at=_OLD_STARTED_AT)

    row = spawn_store.get_spawn(state_root, spawn_id)
    assert row is not None

    reconciled = reconcile_active_spawn(state_root, row)

    assert reconciled.status == "failed"
    assert reconciled.error == "missing_spawn_dir"
    latest = spawn_store.get_spawn(state_root, spawn_id)
    assert latest is not None
    assert latest.status == "failed"


def test_reconcile_active_spawn_marks_missing_pid_files_failed_after_grace(tmp_path: Path) -> None:
    state_root, spawn_id = _start_background_spawn(tmp_path, started_at=_OLD_STARTED_AT)
    spawn_dir = state_root / "spawns" / spawn_id
    spawn_dir.mkdir(parents=True, exist_ok=True)

    row = spawn_store.get_spawn(state_root, spawn_id)
    assert row is not None

    reconciled = reconcile_active_spawn(state_root, row)

    assert reconciled.status == "failed"
    assert reconciled.error == "missing_wrapper_pid"


def test_reconcile_active_spawn_promotes_queued_background_to_running_with_wrapper_pid(tmp_path: Path) -> None:
    state_root, spawn_id = _start_background_spawn(tmp_path, started_at=_OLD_STARTED_AT)
    spawn_dir = state_root / "spawns" / spawn_id
    spawn_dir.mkdir(parents=True, exist_ok=True)
    (spawn_dir / "background.pid").write_text(f"{os.getpid()}\n", encoding="utf-8")

    row = spawn_store.get_spawn(state_root, spawn_id)
    assert row is not None

    reconciled = reconcile_active_spawn(state_root, row)

    assert reconciled.status == "running"
    assert reconciled.wrapper_pid == os.getpid()
    latest = spawn_store.get_spawn(state_root, spawn_id)
    assert latest is not None
    assert latest.status == "running"
    assert latest.wrapper_pid == os.getpid()


def test_reconcile_active_spawn_marks_reported_foreground_spawn_succeeded(tmp_path: Path) -> None:
    state_root = resolve_state_paths(tmp_path).root_dir
    sleeper = subprocess.Popen(["sleep", "30"], start_new_session=True)
    try:
        spawn_id = spawn_store.start_spawn(
            state_root,
            chat_id="c1",
            model="gpt-5.4",
            agent="agent",
            harness="codex",
            kind="child",
            prompt="hello",
            launch_mode="foreground",
            worker_pid=sleeper.pid,
            status="running",
            started_at=_OLD_STARTED_AT,
        )
        spawn_dir = state_root / "spawns" / str(spawn_id)
        spawn_dir.mkdir(parents=True, exist_ok=True)
        (spawn_dir / "harness.pid").write_text(f"{sleeper.pid}\n", encoding="utf-8")
        (spawn_dir / "report.md").write_text("# Finished\n\nCompleted.\n", encoding="utf-8")

        row = spawn_store.get_spawn(state_root, spawn_id)
        assert row is not None

        reconciled = reconcile_active_spawn(state_root, row)

        assert reconciled.status == "succeeded"
        assert reconciled.exit_code == 0
        assert reconciled.error is None
        latest = spawn_store.get_spawn(state_root, spawn_id)
        assert latest is not None
        assert latest.status == "succeeded"
        assert latest.exit_code == 0
        assert latest.error is None
    finally:
        if sleeper.poll() is None:
            sleeper.terminate()
            sleeper.wait(timeout=5)
