from __future__ import annotations

import json

import pytest

from meridian.lib.space.space_file import create_space, get_space, list_spaces, update_space_status


def test_create_space_writes_space_json_and_fs_and_gitignore(tmp_path):
    record = create_space(tmp_path, name="feature-auth")

    space_dir = tmp_path / ".meridian" / ".spaces" / record.id
    assert record.id == "s1"
    assert record.name == "feature-auth"
    assert record.status == "active"
    assert record.finished_at is None
    assert (space_dir / "fs").is_dir()
    assert (tmp_path / ".meridian" / ".gitignore").exists()

    payload = json.loads((space_dir / "space.json").read_text(encoding="utf-8"))
    assert payload == {
        "schema_version": 1,
        "id": "s1",
        "name": "feature-auth",
        "status": "active",
        "created_at": record.created_at,
        "finished_at": None,
    }


def test_get_space_returns_none_when_missing(tmp_path):
    assert get_space(tmp_path, "s404") is None


def test_list_spaces_reads_all_space_json_files(tmp_path):
    create_space(tmp_path, name="one")
    create_space(tmp_path, name="two")

    spaces = list_spaces(tmp_path)
    assert [space.id for space in spaces] == ["s1", "s2"]
    assert [space.name for space in spaces] == ["one", "two"]


def test_update_space_status_under_lock_read_modify_write(tmp_path):
    created = create_space(tmp_path, name="lifecycle")

    closed = update_space_status(tmp_path, created.id, "closed")
    assert closed.status == "closed"
    assert closed.finished_at is not None

    reopened = update_space_status(tmp_path, created.id, "active")
    assert reopened.status == "active"
    assert reopened.finished_at is None
    assert not (tmp_path / ".meridian" / ".spaces" / created.id / "space.json.tmp").exists()


def test_update_space_status_rejects_invalid_status(tmp_path):
    created = create_space(tmp_path)

    with pytest.raises(ValueError, match="active"):
        update_space_status(tmp_path, created.id, "paused")  # type: ignore[arg-type]


def test_update_space_status_requires_existing_space(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        update_space_status(tmp_path, "s9", "closed")
