"""Session policy helpers."""

from __future__ import annotations

import shutil
from pathlib import Path

import structlog

from meridian.lib.state import spawn_store, work_store
from meridian.lib.state.session_store import (
    get_session_active_work_id,
    list_active_sessions,
    update_session_work_id,
)

logger = structlog.get_logger(__name__)


def ensure_session_work_item(
    state_root: Path,
    chat_id: str,
    *,
    inherited_work_id: str | None = None,
) -> str:
    existing_work_id = get_session_active_work_id(state_root, chat_id)
    if existing_work_id:
        return existing_work_id

    # Inherit parent's work item instead of creating a new auto one.
    resolved_inherited = (inherited_work_id or "").strip()
    if resolved_inherited:
        item = work_store.get_work_item(state_root, resolved_inherited)
        if item is not None:
            update_session_work_id(state_root, chat_id, resolved_inherited)
            return resolved_inherited
        logger.warning(
            "Inherited work item not found, creating auto work item.",
            inherited_work_id=resolved_inherited,
            chat_id=chat_id,
        )

    auto_item = work_store.create_auto_work_item(state_root)
    update_session_work_id(state_root, chat_id, auto_item.name)
    return auto_item.name


def cleanup_empty_auto_work_item(state_root: Path, chat_id: str) -> None:
    """Delete this session's auto work item if it has no spawns.

    Called during session teardown. Only removes work items that are
    auto-generated, contain no user files beyond work.json, and have
    zero spawns referencing them.
    """
    work_id = get_session_active_work_id(state_root, chat_id)
    if not work_id:
        return

    item = work_store.get_work_item(state_root, work_id)
    if item is None or not item.auto_generated:
        return

    # Don't delete if another active session is using this work item.
    for active_chat_id in list_active_sessions(state_root):
        if active_chat_id == chat_id:
            continue
        if get_session_active_work_id(state_root, active_chat_id) == work_id:
            return

    # Don't delete if the work dir has user-created files beyond work.json.
    work_dir = state_root / "work" / work_id
    if work_dir.is_dir():
        files = [f for f in work_dir.iterdir() if f.name != "work.json"]
        if files:
            return

    # Don't delete if any spawns reference this work item.
    spawns = spawn_store.list_spawns(state_root, filters={"work_id": work_id})
    if spawns:
        return

    # Safe to remove — auto-generated, empty, no spawns, no other sessions.
    if work_dir.is_dir():
        shutil.rmtree(work_dir, ignore_errors=True)
        logger.debug(
            "Cleaned up empty auto work item.",
            work_id=work_id,
            chat_id=chat_id,
        )


__all__ = ["cleanup_empty_auto_work_item", "ensure_session_work_item"]
