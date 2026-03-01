"""Space CRUD helpers backed by `space.json` files."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from meridian.lib.domain import Space, SpaceState
from meridian.lib.space import space_file
from meridian.lib.space.space_file import SpaceRecord
from meridian.lib.types import SpaceId

_ALLOWED_TRANSITIONS: Mapping[SpaceState, frozenset[SpaceState]] = {
    "active": frozenset({"closed"}),
    "closed": frozenset({"active"}),  # resume reopens a closed space
}


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    try:
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _to_space(record: SpaceRecord) -> Space:
    return Space(
        space_id=SpaceId(record.id),
        state=record.status,
        created_at=_parse_iso_datetime(record.created_at) or datetime.now(UTC),
        finished_at=_parse_iso_datetime(record.finished_at),
        name=record.name,
    )


def create_space(repo_root: Path, *, name: str | None = None) -> Space:
    """Create one active space record."""

    return _to_space(space_file.create_space(repo_root, name=name))


def get_space_or_raise(repo_root: Path, space_id: SpaceId) -> Space:
    """Fetch a space and raise when it does not exist."""

    record = space_file.get_space(repo_root, space_id)
    if record is None:
        raise ValueError(f"Space '{space_id}' not found")
    return _to_space(record)


def resolve_space_for_resume(repo_root: Path, space: str | None) -> SpaceId:
    """Resolve resume target from explicit value or most-recent active space."""

    if space is not None and space.strip():
        return SpaceId(space.strip())

    spaces = space_file.list_spaces(repo_root)
    active = [record for record in spaces if record.status == "active"]
    if active:
        latest_active = max(active, key=lambda record: record.created_at)
        return SpaceId(latest_active.id)

    if not spaces:
        raise ValueError("No space available to resume.")
    latest = max(spaces, key=lambda record: record.created_at)
    return SpaceId(latest.id)


def can_transition(current: SpaceState, new_state: SpaceState) -> bool:
    """Return whether one space lifecycle transition is valid."""

    if current == new_state:
        return True
    return new_state in _ALLOWED_TRANSITIONS[current]


def transition_space(
    repo_root: Path,
    space_id: SpaceId,
    new_state: SpaceState,
) -> Space:
    """Apply a validated space lifecycle transition."""

    space = get_space_or_raise(repo_root, space_id)
    current = space.state
    if not can_transition(current, new_state):
        raise ValueError(
            "Invalid space transition "
            f"'{space_id}': {current} -> {new_state}."
        )

    if current != new_state:
        space_file.update_space_status(repo_root, space_id, new_state)

    return get_space_or_raise(repo_root, space_id)
