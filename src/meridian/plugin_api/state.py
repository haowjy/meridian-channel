"""State-root helpers for plugin-facing APIs."""

from __future__ import annotations

from pathlib import Path

from meridian.lib.state.user_paths import (
    get_project_home as _get_project_home,
)
from meridian.lib.state.user_paths import (
    get_user_home as _get_user_home,
)


def get_user_home() -> Path:
    """Return the user-level state root directory.

    Resolution order:
    1. ``MERIDIAN_HOME`` environment variable when set
    2. Platform default
    """

    return _get_user_home()


def get_project_home(project_uuid: str) -> Path:
    """Return the project-level state root path."""

    return _get_project_home(project_uuid)
