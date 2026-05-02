"""Telemetry initialization helpers for process entry seams."""

from __future__ import annotations

from pathlib import Path

from meridian.lib.telemetry import init_telemetry
from meridian.lib.telemetry.sinks import NoopSink, StderrSink, TelemetrySink


def setup_telemetry(
    *,
    runtime_root: Path | None = None,
    rootless: bool = False,
    sink: TelemetrySink | None = None,
) -> None:
    """Select and install the process telemetry sink."""
    if sink is not None:
        init_telemetry(sink=sink, runtime_root=runtime_root)
        return
    if rootless and runtime_root is None:
        init_telemetry(sink=StderrSink())
        return
    # LocalJSONLSink is introduced in Phase 2.2; runtime-root processes use a
    # placeholder NoopSink for the 2.1 contract.
    init_telemetry(sink=NoopSink(), runtime_root=runtime_root)
