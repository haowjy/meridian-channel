from pathlib import Path

from meridian.lib.ops.work import (
    WorkClearInput,
    WorkDashboardInput,
    WorkDoneInput,
    WorkListInput,
    WorkRenameInput,
    WorkShowInput,
    WorkStartInput,
    WorkSwitchInput,
    WorkUpdateInput,
    work_clear_sync,
    work_dashboard_sync,
    work_done_sync,
    work_list_sync,
    work_rename_sync,
    work_show_sync,
    work_start_sync,
    work_switch_sync,
    work_update_sync,
)
from meridian.lib.state import session_store, spawn_store
from meridian.lib.state.paths import resolve_state_paths


def test_work_rename_updates_spawns_and_session(tmp_path: Path) -> None:
    """Rename propagates to spawns with the old work_id and updates session active_work_id."""
    state_root = resolve_state_paths(tmp_path).root_dir
    chat_id = session_store.start_session(
        state_root,
        harness="codex",
        harness_session_id="session-1",
        model="gpt-5.4",
    )

    started = work_start_sync(
        WorkStartInput(label="Old name", chat_id=chat_id, repo_root=tmp_path.as_posix())
    )

    # Create a spawn tagged with the old work_id
    spawn_store.start_spawn(
        state_root,
        chat_id=chat_id,
        model="gpt-5.4",
        agent="agent",
        harness="codex",
        prompt="task",
        desc="step 1",
        work_id=started.name,
    )

    renamed = work_rename_sync(
        WorkRenameInput(
            work_id=started.name,
            new_name="new-name",
            chat_id=chat_id,
            repo_root=tmp_path.as_posix(),
        )
    )

    assert renamed.old_name == "old-name"
    assert renamed.new_name == "new-name"

    # Spawn should now reference the new work_id
    spawns = spawn_store.list_spawns(state_root, filters={"work_id": "new-name"})
    assert len(spawns) == 1
    assert spawns[0].work_id == "new-name"

    # No spawns should still reference the old work_id
    assert spawn_store.list_spawns(state_root, filters={"work_id": "old-name"}) == []

    # Session active_work_id should be updated
    session = session_store.resolve_session_ref(state_root, "session-1")
    assert session is not None
    assert session.active_work_id == "new-name"

    session_store.stop_session(state_root, chat_id)


def test_work_start_renames_auto_generated_item(tmp_path: Path) -> None:
    """work start renames the active auto-generated item instead of creating a new one."""
    state_root = resolve_state_paths(tmp_path).root_dir
    chat_id = session_store.start_session(
        state_root,
        harness="codex",
        harness_session_id="session-1",
        model="gpt-5.4",
    )

    # Create an auto-generated work item and set it as active
    from meridian.lib.state.work_store import create_auto_work_item, get_work_item
    auto_item = create_auto_work_item(state_root)
    session_store.update_session_work_id(state_root, chat_id, auto_item.name)

    # Write a file to the work dir to prove it persists after rename
    work_dir = state_root / "work" / auto_item.name
    (work_dir / "design.md").write_text("my design doc")

    # Now call work start — should rename, not create new
    started = work_start_sync(
        WorkStartInput(
            label="Auth refactor",
            description="step 1",
            chat_id=chat_id,
            repo_root=tmp_path.as_posix(),
        )
    )

    assert started.name == "auth-refactor"

    # Old directory should be gone, new one should exist with the design doc preserved
    assert not (state_root / "work" / auto_item.name).exists()
    assert (state_root / "work" / "auth-refactor" / "design.md").read_text() == "my design doc"

    # The item should no longer be auto-generated
    item = get_work_item(state_root, "auth-refactor")
    assert item is not None
    assert item.auto_generated is False

    # Session should point to the new name
    session = session_store.resolve_session_ref(state_root, "session-1")
    assert session is not None
    assert session.active_work_id == "auth-refactor"

    session_store.stop_session(state_root, chat_id)


def test_work_rename_preserves_unrelated_session_work_id(tmp_path: Path) -> None:
    """Rename should not overwrite session active_work_id if it points to a different item."""
    state_root = resolve_state_paths(tmp_path).root_dir
    chat_id = session_store.start_session(
        state_root,
        harness="codex",
        harness_session_id="session-1",
        model="gpt-5.4",
    )

    # Create two work items
    first = work_start_sync(
        WorkStartInput(label="Feature A", chat_id=chat_id, repo_root=tmp_path.as_posix())
    )
    second = work_start_sync(
        WorkStartInput(label="Feature B", chat_id=chat_id, repo_root=tmp_path.as_posix())
    )

    # Session now points to the second work item (last started)
    session = session_store.resolve_session_ref(state_root, "session-1")
    assert session is not None
    assert session.active_work_id == second.name

    # Rename the first work item — should NOT change the session's active_work_id
    work_rename_sync(
        WorkRenameInput(
            work_id=first.name,
            new_name="feature-a-renamed",
            chat_id=chat_id,
            repo_root=tmp_path.as_posix(),
        )
    )

    session = session_store.resolve_session_ref(state_root, "session-1")
    assert session is not None
    assert session.active_work_id == second.name  # Should still point to feature-b

    session_store.stop_session(state_root, chat_id)
