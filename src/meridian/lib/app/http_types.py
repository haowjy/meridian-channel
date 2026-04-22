"""Shared HTTP type definitions for app routes."""

from __future__ import annotations

from typing import Protocol


class HTTPExceptionCallable(Protocol):
    """Protocol for HTTP exception factory callables."""

    def __call__(
        self,
        status_code: int,
        detail: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> Exception: ...
