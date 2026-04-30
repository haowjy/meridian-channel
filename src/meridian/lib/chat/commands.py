"""Shared inbound chat command vocabulary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final, Literal

COMMAND_PROMPT: Final = "prompt"
COMMAND_CANCEL: Final = "cancel"
COMMAND_APPROVE: Final = "approve"
COMMAND_ANSWER_INPUT: Final = "answer_input"
COMMAND_CLOSE: Final = "close"
COMMAND_REVERT: Final = "revert"
COMMAND_SWAP_MODEL: Final = "swap_model"
COMMAND_SWAP_EFFORT: Final = "swap_effort"

SUPPORTED_COMMAND_TYPES: Final = frozenset(
    {
        COMMAND_PROMPT,
        COMMAND_CANCEL,
        COMMAND_APPROVE,
        COMMAND_ANSWER_INPUT,
        COMMAND_CLOSE,
        COMMAND_REVERT,
        COMMAND_SWAP_MODEL,
        COMMAND_SWAP_EFFORT,
    }
)

@dataclass(frozen=True)
class ChatCommand:
    """One inbound command from any consumer."""

    type: str
    command_id: str
    chat_id: str
    timestamp: str
    payload: dict[str, Any] = field(default_factory=lambda: {})

@dataclass(frozen=True)
class CommandResult:
    """Synchronous acknowledgment for a dispatched command."""

    status: Literal["accepted", "rejected"]
    error: str | None = None

__all__ = [
    "COMMAND_ANSWER_INPUT",
    "COMMAND_APPROVE",
    "COMMAND_CANCEL",
    "COMMAND_CLOSE",
    "COMMAND_PROMPT",
    "COMMAND_REVERT",
    "COMMAND_SWAP_EFFORT",
    "COMMAND_SWAP_MODEL",
    "SUPPORTED_COMMAND_TYPES",
    "ChatCommand",
    "CommandResult",
]
