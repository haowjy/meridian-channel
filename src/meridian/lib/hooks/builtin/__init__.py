"""Builtin hook registry."""

from meridian.lib.hooks.builtin.base import BuiltinHook
from meridian.lib.hooks.builtin.git_autosync import GIT_AUTOSYNC

BUILTIN_HOOKS: dict[str, BuiltinHook] = {
    GIT_AUTOSYNC.name: GIT_AUTOSYNC,
}

__all__ = ["BUILTIN_HOOKS", "BuiltinHook"]
