from __future__ import annotations

import signal
from typing import Any

import pytest

from meridian.lib.launch.process import pty_launcher


@pytest.mark.unit
def test_install_winsize_forwarding_skips_signal_handlers_off_main_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sync_calls: list[tuple[int, int]] = []
    signal_calls: list[int] = []
    fake_main_thread = object()
    fake_worker_thread = object()

    def _fake_sync_pty_winsize(*, source_fd: int, target_fd: int) -> None:
        sync_calls.append((source_fd, target_fd))

    def _fake_getsignal(_sig: int) -> signal.Handlers:
        signal_calls.append(signal.SIGWINCH)
        return signal.SIG_DFL

    def _fake_signal(_sig: int, _handler: Any) -> None:
        signal_calls.append(signal.SIGWINCH)

    monkeypatch.setattr(pty_launcher, "_sync_pty_winsize", _fake_sync_pty_winsize)
    monkeypatch.setattr(pty_launcher.threading, "main_thread", lambda: fake_main_thread)
    monkeypatch.setattr(pty_launcher.threading, "current_thread", lambda: fake_worker_thread)
    monkeypatch.setattr(pty_launcher.signal, "getsignal", _fake_getsignal)
    monkeypatch.setattr(pty_launcher.signal, "signal", _fake_signal)

    restore = pty_launcher._install_winsize_forwarding(source_fd=10, target_fd=20)
    restore()

    assert sync_calls == [(10, 20)]
    assert signal_calls == []
