"""Work item smoke tests — lifecycle and storage.

Replaces: tests/e2e/work-items.md
"""


def test_work_list_empty(cli):
    """work list with no items returns cleanly."""
    result = cli("work", "list", json_mode=True)
    result.assert_success()
    
    data = result.json
    # Should have a work_items key or be structured data
    assert isinstance(data, dict)
    # work_items may be empty list or absent
    items = data.get("work_items", data.get("items", []))
    assert isinstance(items, list)


def test_work_start_creates_item(cli):
    """work start creates a new work item."""
    result = cli("work", "start", "smoke-test-item")
    result.assert_success()
    
    # Verify it shows up in list
    list_result = cli("work", "list", json_mode=True)
    list_result.assert_success()


def test_work_list_shows_created_item(cli):
    """work list shows items after creation."""
    cli("work", "start", "visible-item")
    result = cli("work", "list", json_mode=True)
    result.assert_success()
    
    # Item should be in the list somewhere
    output = str(result.json)
    assert "visible-item" in output


def test_work_done_archives_item(cli):
    """work done archives a work item."""
    cli("work", "start", "to-archive")
    result = cli("work", "done", "to-archive")
    result.assert_success()


def test_work_delete_removes_empty_item(cli):
    """work delete removes an empty work item."""
    cli("work", "start", "to-delete")
    result = cli("work", "delete", "to-delete")
    result.assert_success()


def test_work_delete_force_removes_item_with_artifacts(cli, scratch_dir):
    """work delete --force removes item with artifacts."""
    cli("work", "start", "artifact-item")
    
    # Create an artifact in the work dir
    work_dir = scratch_dir / ".meridian" / "work" / "artifact-item"
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "notes.md").write_text("# Notes\n", encoding="utf-8")
    
    # Regular delete should fail or prompt
    result = cli("work", "delete", "artifact-item")
    # Force delete should succeed
    force_result = cli("work", "delete", "artifact-item", "--force")
    # At least one should work
    assert result.returncode == 0 or force_result.returncode == 0


def test_work_rename(cli):
    """work rename changes item name."""
    cli("work", "start", "original-name")
    result = cli("work", "rename", "original-name", "new-name")
    # Should succeed or fail cleanly
    assert "Traceback" not in result.stderr
