from __future__ import annotations

import signal
from pathlib import Path

from meridian.lib.launch import process
from meridian.lib.launch.command import PrimaryHarnessContext
from meridian.lib.launch.process import LaunchContext
from meridian.lib.launch.types import LaunchRequest, PrimarySessionMetadata
from meridian.lib.config.settings import load_config
from meridian.lib.harness.registry import get_default_harness_registry


def test_sync_pty_winsize_copies_source_size(monkeypatch) -> None:
    calls: list[tuple[int, int, bytes]] = []
    packed = b"winsize-bytes"

    def fake_ioctl(fd: int, op: int, payload: bytes) -> bytes:
        calls.append((fd, op, payload))
        if op == process.termios.TIOCGWINSZ:
            return packed
        return b""

    monkeypatch.setattr(process.fcntl, "ioctl", fake_ioctl)

    process._sync_pty_winsize(source_fd=10, target_fd=11)

    assert calls == [
        (10, process.termios.TIOCGWINSZ, process.struct.pack("HHHH", 0, 0, 0, 0)),
        (11, process.termios.TIOCSWINSZ, packed),
    ]


def test_install_winsize_forwarding_syncs_immediately_and_restores(monkeypatch) -> None:
    sync_calls: list[tuple[int, int]] = []
    installed_handlers: list[tuple[int, object]] = []
    previous_handler = signal.SIG_IGN

    monkeypatch.setattr(
        process,
        "_sync_pty_winsize",
        lambda *, source_fd, target_fd: sync_calls.append((source_fd, target_fd)),
    )
    monkeypatch.setattr(process.signal, "getsignal", lambda signum: previous_handler)
    monkeypatch.setattr(
        process.signal,
        "signal",
        lambda signum, handler: installed_handlers.append((signum, handler)),
    )

    restore = process._install_winsize_forwarding(source_fd=20, target_fd=21)

    assert sync_calls == [(20, 21)]
    assert installed_handlers[0][0] == signal.SIGWINCH

    handler = installed_handlers[0][1]
    assert callable(handler)
    handler(signal.SIGWINCH, None)

    assert sync_calls == [(20, 21), (20, 21)]

    restore()

    assert installed_handlers[-1] == (signal.SIGWINCH, previous_handler)


def test_run_harness_process_reuses_tracked_chat_id_on_resume(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    harness_registry = get_default_harness_registry()
    config = load_config(repo_root)
    request = LaunchRequest(
        model="gpt-5.4",
        harness="codex",
        fresh=False,
        continue_harness_session_id="session-2",
        continue_chat_id="c7",
    )
    ctx = LaunchContext(
        config=config,
        prompt="resume prompt",
        session_metadata=PrimarySessionMetadata(
            harness="codex",
            model="gpt-5.4",
            agent="",
            agent_path="",
            skills=(),
            skill_paths=(),
        ),
        state_root=tmp_path / ".meridian",
        lock_path=tmp_path / ".meridian" / "active-primary.lock",
        seed_harness_session_id="session-2",
        command_request=request,
    )

    captured: dict[str, object] = {}

    monkeypatch.setattr(process, "_sweep_orphaned_materializations", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        process,
        "build_harness_context",
        lambda **kwargs: PrimaryHarnessContext(command=("true",)),
    )
    monkeypatch.setattr(process, "build_launch_env", lambda *args, **kwargs: {})
    monkeypatch.setattr(process, "_run_primary_process_with_capture", lambda **kwargs: (0, 123))
    monkeypatch.setattr(process, "extract_latest_session_id", lambda **kwargs: "session-2")
    monkeypatch.setattr(process, "stop_session", lambda *args, **kwargs: None)
    monkeypatch.setattr(process, "update_session_harness_id", lambda *args, **kwargs: None)

    def fake_start_session(state_root, harness, harness_session_id, model, chat_id=None, **kwargs):
        captured["chat_id_arg"] = chat_id
        return chat_id or "c999"

    monkeypatch.setattr(process, "start_session", fake_start_session)

    outcome = process.run_harness_process(repo_root, request, ctx, harness_registry)

    assert captured["chat_id_arg"] == "c7"
    assert outcome.chat_id == "c7"
