"""Session policy helpers."""

from __future__ import annotations

from pathlib import Path

from meridian.lib.state import work_store
from meridian.lib.state.session_store import get_session_active_work_id, update_session_work_id


def ensure_session_work_item(state_root: Path, chat_id: str) -> str:
    existing_work_id = get_session_active_work_id(state_root, chat_id)
    if existing_work_id:
        return existing_work_id

    auto_item = work_store.create_auto_work_item(state_root)
    update_session_work_id(state_root, chat_id, auto_item.name)
    return auto_item.name


__all__ = ["ensure_session_work_item"]
