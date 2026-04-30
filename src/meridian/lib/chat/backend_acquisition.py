"""Backend acquisition strategy boundary for chat sessions."""

from __future__ import annotations

from typing import Protocol

from meridian.lib.chat.backend_handle import BackendHandle


class BackendAcquisition(Protocol):
    """Strategy for acquiring a backing execution on first prompt."""

    async def acquire(self, chat_id: str, initial_prompt: str) -> BackendHandle:
        """Acquire a backend and send the initial prompt as part of startup."""
        ...

__all__ = ["BackendAcquisition"]
