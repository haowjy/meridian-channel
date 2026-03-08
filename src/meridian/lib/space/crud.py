"""Compatibility shim for space CRUD helpers."""

from meridian.lib.ops.space import create_space, get_space_or_raise, resolve_space_for_resume

__all__ = ["create_space", "get_space_or_raise", "resolve_space_for_resume"]
