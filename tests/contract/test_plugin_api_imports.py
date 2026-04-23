from __future__ import annotations

import meridian.plugin_api as plugin_api
from meridian.plugin_api import (
    FailurePolicy,
    Hook,
    HookContext,
    HookEventName,
    HookOutcome,
    HookResult,
    __version__,
    get_project_home,
    get_user_home,
)


def test_plugin_api_exports_match_stable_contract() -> None:
    """Pin the public surface — only hook types and state helpers."""

    assert plugin_api.__all__ == [
        "FailurePolicy",
        "Hook",
        "HookContext",
        "HookEventName",
        "HookOutcome",
        "HookResult",
        "__version__",
        "get_project_home",
        "get_user_home",
    ]


def test_plugin_api_stable_exports_are_importable() -> None:
    assert FailurePolicy is not None
    assert Hook is not None
    assert HookContext is not None
    assert HookEventName is not None
    assert HookOutcome is not None
    assert HookResult is not None
    assert isinstance(__version__, str)
    assert callable(get_project_home)
    assert callable(get_user_home)


def test_unstable_helpers_not_reexported() -> None:
    """Utility functions must be imported from submodules, not the top-level package."""

    assert not hasattr(plugin_api, "file_lock")
    assert not hasattr(plugin_api, "generate_repo_slug")
    assert not hasattr(plugin_api, "normalize_repo_url")
    assert not hasattr(plugin_api, "resolve_clone_path")
    assert not hasattr(plugin_api, "get_git_overrides")
    assert not hasattr(plugin_api, "get_user_config")
