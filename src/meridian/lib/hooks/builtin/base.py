"""Builtin hook protocol contracts."""

from __future__ import annotations

from typing import Protocol

from meridian.lib.hooks.types import Hook, HookContext, HookResult


class BuiltinHook(Protocol):
    """Protocol implemented by in-process built-in hooks."""

    name: str
    requirements: tuple[str, ...]
    default_events: tuple[str, ...]
    default_interval: str | None

    def check_requirements(self) -> tuple[bool, str | None]:
        """Return whether runtime requirements are available."""
        ...

    def execute(self, context: HookContext, config: Hook) -> HookResult:
        """Execute one hook invocation."""
        ...
