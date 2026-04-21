"""Builtin hook protocol contracts."""

from __future__ import annotations

from typing import Protocol

from meridian.plugin_api import Hook, HookContext, HookResult


class BuiltinHook(Protocol):
    """Protocol implemented by in-process built-in hooks."""

    name: str
    requirements: tuple[str, ...]

    @property
    def default_events(self) -> tuple[str, ...]:
        """Default lifecycle events for this builtin hook."""
        ...

    @property
    def default_interval(self) -> str | None:
        """Default throttle interval for this builtin hook."""
        ...

    def check_requirements(self) -> tuple[bool, str | None]:
        """Return whether runtime requirements are available."""
        ...

    def execute(self, context: HookContext, config: Hook) -> HookResult:
        """Execute one hook invocation."""
        ...
