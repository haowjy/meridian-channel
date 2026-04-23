"""Retry-classified connection startup failures."""


class ConnectionStartupError(RuntimeError):
    """Base class for connection startup failures."""


class RetryableConnectionStartupError(ConnectionStartupError):
    """Startup failure that can be retried with new config."""


class PortBindError(RetryableConnectionStartupError):
    """Backend failed to bind pre-reserved loopback port (TOCTOU race)."""


__all__ = [
    "ConnectionStartupError",
    "PortBindError",
    "RetryableConnectionStartupError",
]
