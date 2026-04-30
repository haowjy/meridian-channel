"""TUI passthrough for managed primary sessions."""

from meridian.lib.harness.passthrough.base import TuiPassthrough
from meridian.lib.harness.passthrough.registry import get_passthrough

__all__ = ["TuiPassthrough", "get_passthrough"]
