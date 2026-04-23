"""Canonical helpers for Meridian delegation depth."""

import os
from collections.abc import Mapping
from contextlib import suppress

MERIDIAN_DEPTH_ENV = "MERIDIAN_DEPTH"


def parse_meridian_depth(raw: str | None) -> int:
    """Parse a ``MERIDIAN_DEPTH`` value as a non-negative integer."""
    value = (raw or "0").strip()
    with suppress(ValueError, TypeError):
        return max(0, int(value))
    return 0


def current_meridian_depth(env: Mapping[str, str] | None = None) -> int:
    """Return the current process's normalized Meridian depth."""
    source = os.environ if env is None else env
    return parse_meridian_depth(source.get(MERIDIAN_DEPTH_ENV))


def child_meridian_depth(parent_depth: int, *, increment_depth: bool = True) -> int:
    """Return the depth to project into a child process."""
    normalized = max(0, parent_depth)
    return normalized + 1 if increment_depth else normalized


def is_nested_meridian_depth(depth: int) -> bool:
    """Return whether a depth represents execution below the primary root."""
    return depth > 0


def is_nested_meridian_process(env: Mapping[str, str] | None = None) -> bool:
    """Return whether the current environment is inside delegated Meridian execution."""
    return is_nested_meridian_depth(current_meridian_depth(env))


def max_depth_reached(current_depth: int, max_depth: int) -> bool:
    """Return whether creating another depth-child would exceed the configured ceiling."""
    if max_depth < 0:
        raise ValueError("max_depth must be >= 0.")
    return current_depth >= max_depth


__all__ = [
    "MERIDIAN_DEPTH_ENV",
    "child_meridian_depth",
    "current_meridian_depth",
    "is_nested_meridian_depth",
    "is_nested_meridian_process",
    "max_depth_reached",
    "parse_meridian_depth",
]
