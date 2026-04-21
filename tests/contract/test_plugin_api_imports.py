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
    file_lock,
    generate_repo_slug,
    get_git_overrides,
    get_project_state_root,
    get_user_config,
    get_user_state_root,
    normalize_repo_url,
    resolve_clone_path,
)


def test_plugin_api_exports_match_documented_contract() -> None:
    assert plugin_api.__all__ == [
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
        "get_project_state_root",
        "get_user_config",
        "get_user_state_root",
        "normalize_repo_url",
        "resolve_clone_path",
    ]


def test_plugin_api_documented_exports_are_importable() -> None:
    assert FailurePolicy is not None
    assert Hook is not None
    assert HookContext is not None
    assert HookEventName is not None
    assert HookOutcome is not None
    assert HookResult is not None
    assert isinstance(__version__, str)
    assert callable(file_lock)
    assert callable(generate_repo_slug)
    assert callable(get_git_overrides)
    assert callable(get_project_state_root)
    assert callable(get_user_config)
    assert callable(get_user_state_root)
    assert callable(normalize_repo_url)
    assert callable(resolve_clone_path)
