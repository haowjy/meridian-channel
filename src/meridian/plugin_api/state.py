"""State-root helpers for plugin-facing APIs."""

from __future__ import annotations

from pathlib import Path

from meridian.lib.state.user_paths import (
    get_project_state_root as _get_project_state_root,
)
from meridian.lib.state.user_paths import (
    get_user_state_root as _get_user_state_root,
)


def get_user_state_root() -> Path:
    """Return the user-level state root directory.

    Resolution order:
    1. ``MERIDIAN_HOME`` environment variable when set
    2. Platform default
    """

    return _get_user_state_root()


def get_project_state_root(project_uuid: str) -> Path:
    """Return the project-level state root path."""

    return _get_project_state_root(project_uuid)

