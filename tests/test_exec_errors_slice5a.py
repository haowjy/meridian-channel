"""Slice 5a error classification tests."""

from __future__ import annotations

from meridian.lib.exec.errors import ErrorCategory, classify_error, should_retry


def test_classify_error_token_limit_unrecoverable() -> None:
    category = classify_error(1, "Request failed: token limit exceeded for this model.")
    assert category == ErrorCategory.UNRECOVERABLE


def test_classify_error_model_not_found_unrecoverable() -> None:
    category = classify_error(1, "Model not found: gpt-unknown")
    assert category == ErrorCategory.UNRECOVERABLE


def test_classify_error_network_retryable() -> None:
    category = classify_error(1, "Network error: connection reset by peer")
    assert category == ErrorCategory.RETRYABLE


def test_classify_error_context_overflow_strategy_change() -> None:
    category = classify_error(1, "Maximum context length exceeded; prompt too long.")
    assert category == ErrorCategory.STRATEGY_CHANGE


def test_should_retry_honors_retryable_and_max_limit() -> None:
    assert (
        should_retry(
            exit_code=1,
            stderr="network error: connection reset",
            retries_attempted=0,
            max_retries=3,
        )
        is True
    )
    assert (
        should_retry(
            exit_code=1,
            stderr="network error: connection reset",
            retries_attempted=3,
            max_retries=3,
        )
        is False
    )
    assert (
        should_retry(
            exit_code=1,
            stderr="model not found",
            retries_attempted=0,
            max_retries=3,
        )
        is False
    )
