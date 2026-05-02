"""Telemetry sink protocol and simple sink implementations."""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from typing import Protocol

from meridian.lib.telemetry.events import TelemetryEnvelope


class TelemetrySink(Protocol):
    """Best-effort telemetry event sink."""

    def write_batch(self, events: Sequence[TelemetryEnvelope]) -> None:
        """Write a batch of events."""
        ...

    def close(self) -> None:
        """Flush and release resources. Idempotent."""
        ...


class NoopSink:
    """Sink that discards all events."""

    def write_batch(self, events: Sequence[TelemetryEnvelope]) -> None:
        """Discard a batch of events."""
        _ = events

    def close(self) -> None:
        """No-op close."""


class StderrSink:
    """Structured JSON telemetry to stderr for rootless processes."""

    def write_batch(self, events: Sequence[TelemetryEnvelope]) -> None:
        """Write compact JSON envelopes to stderr."""
        for event in events:
            print(json.dumps(event.to_dict(), separators=(",", ":")), file=sys.stderr)

    def close(self) -> None:
        """No-op close."""
