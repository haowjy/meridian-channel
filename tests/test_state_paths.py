from __future__ import annotations

from meridian.lib.exec.spawn import run_log_dir
from meridian.lib.state.db import resolve_run_log_dir, resolve_state_paths
from meridian.lib.types import RunId, WorkspaceId


def test_resolve_state_paths_defaults_to_repo_meridian(tmp_path):
    paths = resolve_state_paths(tmp_path)

    assert paths.root_dir == tmp_path / ".meridian"
    assert paths.index_dir == tmp_path / ".meridian" / "index"
    assert paths.db_path == tmp_path / ".meridian" / "index" / "runs.db"
    assert paths.jsonl_path == tmp_path / ".meridian" / "index" / "runs.jsonl"
    assert paths.lock_path == tmp_path / ".meridian" / "index" / "runs.lock"
    assert paths.artifacts_dir == tmp_path / ".meridian" / "artifacts"
    assert paths.runs_dir == tmp_path / ".meridian" / "runs"
    assert paths.workspaces_dir == tmp_path / ".meridian" / "workspaces"
    assert paths.active_workspaces_dir == tmp_path / ".meridian" / "active-workspaces"
    assert paths.config_path == tmp_path / ".meridian" / "config.toml"
    assert paths.models_path == tmp_path / ".meridian" / "models.toml"


def test_resolve_state_paths_honors_state_root_override(tmp_path, monkeypatch):
    state_root = tmp_path / "state-root"
    monkeypatch.setenv("MERIDIAN_STATE_ROOT", str(state_root))

    paths = resolve_state_paths(tmp_path)

    assert paths.root_dir == state_root
    assert paths.db_path == state_root / "index" / "runs.db"
    assert paths.artifacts_dir == state_root / "artifacts"
    assert paths.config_path == state_root / "config.toml"
    assert paths.models_path == state_root / "models.toml"


def test_run_log_dir_is_centralized(tmp_path):
    run_id = RunId("w1/r7")
    workspace_id = WorkspaceId("w1")

    assert run_log_dir(tmp_path, run_id, None) == resolve_run_log_dir(tmp_path, run_id, None)
    assert run_log_dir(tmp_path, run_id, workspace_id) == resolve_run_log_dir(
        tmp_path, run_id, workspace_id
    )

