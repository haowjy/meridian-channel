from pathlib import Path

import meridian.lib.ops.spawn.api as spawn_api
from meridian.lib.ops.spawn.models import SpawnListInput, SpawnShowInput
from meridian.lib.state import spawn_store
from meridian.lib.state.paths import resolve_state_paths


def _state_root(repo_root: Path) -> Path:
    state_root = resolve_state_paths(repo_root).root_dir
    state_root.mkdir(parents=True, exist_ok=True)
    return state_root


def _seed_terminal_spawn(state_root: Path, spawn_id: str) -> None:
    spawn_store.start_spawn(
        state_root,
        spawn_id=spawn_id,
        chat_id="c1",
        model="gpt-5.3-codex",
        agent="coder",
        harness="codex",
        prompt="hello",
    )
    spawn_store.finalize_spawn(
        state_root,
        spawn_id,
        status="failed",
        exit_code=143,
        error="terminated",
    )


def _write_runtime_files(state_root: Path, spawn_id: str) -> None:
    spawn_dir = state_root / "spawns" / spawn_id
    spawn_dir.mkdir(parents=True, exist_ok=True)
    for name in ("harness.pid", "heartbeat", "background.pid"):
        (spawn_dir / name).write_text("123\n", encoding="utf-8")


def test_spawn_show_sync_cleans_terminal_runtime_files(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    state_root = _state_root(repo_root)
    _seed_terminal_spawn(state_root, "p1")
    _write_runtime_files(state_root, "p1")

    output = spawn_api.spawn_show_sync(
        SpawnShowInput(
            spawn_id="p1",
            include_report_body=False,
            repo_root=repo_root.as_posix(),
        )
    )

    assert output.spawn_id == "p1"
    spawn_dir = state_root / "spawns" / "p1"
    assert not (spawn_dir / "harness.pid").exists()
    assert not (spawn_dir / "heartbeat").exists()
    assert not (spawn_dir / "background.pid").exists()


def test_spawn_list_sync_cleans_terminal_runtime_files_even_when_filtered_out(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    state_root = _state_root(repo_root)
    _seed_terminal_spawn(state_root, "p2")
    _write_runtime_files(state_root, "p2")

    output = spawn_api.spawn_list_sync(SpawnListInput(repo_root=repo_root.as_posix()))

    assert output.spawns == ()
    spawn_dir = state_root / "spawns" / "p2"
    assert not (spawn_dir / "harness.pid").exists()
    assert not (spawn_dir / "heartbeat").exists()
    assert not (spawn_dir / "background.pid").exists()
