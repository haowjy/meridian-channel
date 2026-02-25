"""Harness error classification for retry decisions."""

from __future__ import annotations

from enum import StrEnum


class ErrorCategory(StrEnum):
    RETRYABLE = "retryable"
    UNRECOVERABLE = "unrecoverable"
    STRATEGY_CHANGE = "strategy_change"


_RETRYABLE_MARKERS: tuple[str, ...] = (
    "rate limit",
    "429",
    "timed out",
    "timeout",
    "temporarily unavailable",
    "temporary failure",
    "connection reset",
    "connection refused",
    "network error",
    "econnreset",
    "econnrefused",
    "etimedout",
    "resource busy",
    "database is locked",
)

_UNRECOVERABLE_MARKERS: tuple[str, ...] = (
    "model not found",
    "unknown model",
    "unsupported model",
    "permission denied",
    "access denied",
    "forbidden",
    "unauthorized",
    "invalid api key",
    "authentication failed",
    "token limit",
    "maximum tokens",
    "max tokens exceeded",
)

_STRATEGY_CHANGE_MARKERS: tuple[str, ...] = (
    "context length",
    "context too long",
    "maximum context length",
    "prompt too long",
    "output too large",
    "response too large",
    "please reduce",
)


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def classify_error(exit_code: int, stderr: str) -> ErrorCategory:
    """Classify one failed harness attempt into a retry strategy category."""

    normalized = stderr.lower()

    # Context/output size issues need a different prompt strategy, not blind retries.
    if _contains_any(normalized, _STRATEGY_CHANGE_MARKERS):
        return ErrorCategory.STRATEGY_CHANGE
    if _contains_any(normalized, _UNRECOVERABLE_MARKERS):
        return ErrorCategory.UNRECOVERABLE
    if _contains_any(normalized, _RETRYABLE_MARKERS):
        return ErrorCategory.RETRYABLE

    if exit_code in {3}:
        return ErrorCategory.RETRYABLE
    if exit_code in {130, 143}:
        return ErrorCategory.UNRECOVERABLE
    if exit_code in {1, 2}:
        return ErrorCategory.RETRYABLE
    return ErrorCategory.UNRECOVERABLE


def should_retry(
    *,
    exit_code: int,
    stderr: str,
    retries_attempted: int,
    max_retries: int = 3,
) -> bool:
    if retries_attempted >= max_retries:
        return False
    return classify_error(exit_code, stderr) == ErrorCategory.RETRYABLE
