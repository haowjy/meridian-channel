"""Shared formatting protocol and context for output models.

Lives in the lib layer so both domain types (lib/) and CLI code (cli/)
can depend on it without introducing lib -> cli imports.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict


class FormatContext(BaseModel):
    """Parameters passed to text formatters.

    Provides a stable extension point so format_text() signatures never need
    to change when new formatting knobs are added (verbosity, width, etc.).
    """

    model_config = ConfigDict(frozen=True)

    verbosity: int = 0  # 0=normal, 1=verbose, -1=quiet
    width: int = 80  # terminal column width hint


@runtime_checkable
class TextFormattable(Protocol):
    """Protocol for output models that provide a human-readable text format."""

    def format_text(self, ctx: FormatContext | None = None) -> str: ...
