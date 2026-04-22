"""Meridian Plugin API.

Stable interface for hooks and plugins.
"""

from __future__ import annotations

from meridian.plugin_api.config import get_git_overrides, get_user_config
from meridian.plugin_api.fs import file_lock
from meridian.plugin_api.git import generate_repo_slug, normalize_repo_url, resolve_clone_path
from meridian.plugin_api.state import (
    get_project_home,
    get_project_data_root,
    get_user_home,
    get_meridian_home,
)
from meridian.plugin_api.types import (
    FailurePolicy,
    Hook,
    HookContext,
    HookEventName,
    HookOutcome,
    HookResult,
)

__version__ = "1.0.0"

# Keep new names available as module attributes during rename transition.
_ = (get_project_home, get_user_home)

__all__ = [
    "FailurePolicy",
    "Hook",
    "HookContext",
    "HookEventName",
    "HookOutcome",
    "HookResult",
    "__version__",
    "file_lock",
    "generate_repo_slug",
    "get_git_overrides",
    "get_project_data_root",
    "get_user_config",
    "get_meridian_home",
    "normalize_repo_url",
    "resolve_clone_path",
]
