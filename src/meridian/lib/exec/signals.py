"""Signal forwarding utilities for run execution."""

from __future__ import annotations

import asyncio
import signal
from types import FrameType
from typing import Final, cast

TARGET_SIGNALS: Final[tuple[signal.Signals, ...]] = (signal.SIGINT, signal.SIGTERM)


def signal_to_exit_code(received_signal: signal.Signals | None) -> int | None:
    """Map forwarded signal to documented meridian exit code."""

    if received_signal == signal.SIGINT:
        return 130
    if received_signal == signal.SIGTERM:
        return 143
    return None


def map_process_exit_code(
    *,
    raw_return_code: int,
    received_signal: signal.Signals | None,
) -> int:
    """Map raw subprocess return code + forwarded signal to meridian semantics."""

    signaled_exit = signal_to_exit_code(received_signal)
    if signaled_exit is not None:
        return signaled_exit

    if raw_return_code == 0:
        return 0

    if raw_return_code < 0:
        try:
            signum = signal.Signals(-raw_return_code)
        except ValueError:
            return 1
        mapped = signal_to_exit_code(signum)
        if mapped is not None:
            return mapped
    return 1


class SignalForwarder:
    """Scoped SIGINT/SIGTERM forwarding from parent process to child process."""

    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self._process = process
        self._previous_handlers: dict[signal.Signals, signal.Handlers] = {}
        self._received_signal: signal.Signals | None = None
        self._seen_signal_count = 0

    @property
    def received_signal(self) -> signal.Signals | None:
        return self._received_signal

    def __enter__(self) -> SignalForwarder:
        for signum in TARGET_SIGNALS:
            previous = cast("signal.Handlers", signal.getsignal(signum))
            self._previous_handlers[signum] = previous
            signal.signal(signum, self._on_signal)
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        _ = (exc_type, exc, tb)
        for signum, handler in self._previous_handlers.items():
            signal.signal(signum, handler)
        self._previous_handlers.clear()

    def forward_signal(self, signum: signal.Signals) -> None:
        """Forward one signal to the child and remember it for exit-code mapping."""

        self._received_signal = signum
        self._seen_signal_count += 1

        if self._process.returncode is None:
            try:
                self._process.send_signal(signum)
            except ProcessLookupError:
                return

        if self._seen_signal_count >= 2 and self._process.returncode is None:
            # Second termination signal means "force stop now".
            self._process.kill()

    def _on_signal(self, raw_signum: int, frame: FrameType | None) -> None:
        _ = frame
        self.forward_signal(signal.Signals(raw_signum))
