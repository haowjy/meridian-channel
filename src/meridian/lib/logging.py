"""Structlog configuration helpers."""

from __future__ import annotations

import logging as std_logging

import structlog


def _level_from_verbosity(verbosity: int) -> int:
    if verbosity <= 0:
        return std_logging.WARNING
    if verbosity == 1:
        return std_logging.INFO
    return std_logging.DEBUG


def configure_logging(json_mode: bool = False, verbosity: int = 0) -> None:
    """Configure structlog for CLI or MCP server mode."""

    level = _level_from_verbosity(verbosity)
    std_logging.basicConfig(level=level, format="%(message)s")

    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer() if json_mode else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )
