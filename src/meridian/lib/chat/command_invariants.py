"""Reusable command validation guards."""

from __future__ import annotations

from meridian.lib.chat.backend_handle import BackendHandle
from meridian.lib.chat.session_service import ChatSessionService, ChatState


class CommandInvariantError(RuntimeError):
    """Base class for command invariant failures."""


class NoActiveExecutionError(CommandInvariantError):
    def __init__(self, chat_id: str) -> None:
        super().__init__("no_active_execution")
        self.chat_id = chat_id


class InvalidStateError(CommandInvariantError):
    def __init__(self, chat_id: str, state: ChatState, allowed: tuple[ChatState, ...]) -> None:
        allowed_text = ",".join(allowed)
        super().__init__(f"invalid_state:{state}:expected:{allowed_text}")
        self.chat_id = chat_id
        self.state = state
        self.allowed = allowed


def require_active_execution(session: ChatSessionService) -> BackendHandle:
    handle = session.current_execution
    if handle is None:
        raise NoActiveExecutionError(session.chat_id)
    return handle


def require_state(session: ChatSessionService, *allowed: ChatState) -> None:
    if session.state not in allowed:
        raise InvalidStateError(session.chat_id, session.state, allowed)

__all__ = [
    "CommandInvariantError",
    "InvalidStateError",
    "NoActiveExecutionError",
    "require_active_execution",
    "require_state",
]
