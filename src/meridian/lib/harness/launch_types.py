"""Neutral launch types shared between harness adapters and launch orchestration.

Placed in ``meridian.lib.harness`` (not ``meridian.lib.space``) to avoid
import-cycle pressure from ``space/__init__.py`` which eagerly imports
``space.launch``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SessionSeed:
    """Adapter's session decisions, resolved early (before process starts)."""

    session_id: str = ""
    session_args: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PromptPolicy:
    """Adapter's prompt decisions, resolved during command assembly."""

    prompt: str = ""
    skill_injection: str | None = None
