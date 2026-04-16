from __future__ import annotations

import json

# pyright: reportPrivateUsage=false
import re
import signal
from pathlib import Path
from typing import Any

import pytest

from meridian.lib.config.settings import load_config
from meridian.lib.core.types import HarnessId, ModelId
from meridian.lib.harness.adapter import SpawnParams
from meridian.lib.harness.registry import get_default_harness_registry
from meridian.lib.launch import process
from meridian.lib.launch.constants import DEFAULT_INFRA_EXIT_CODE
from meridian.lib.launch.context import build_launch_context
from meridian.lib.launch.plan import ResolvedPrimaryLaunchPlan
from meridian.lib.launch.request import LaunchRuntime, SessionRequest, SpawnRequest
from meridian.lib.launch.types import LaunchRequest, PrimarySessionMetadata, SessionMode
from meridian.lib.safety.permissions import PermissionConfig, TieredPermissionResolver


def test_sync_pty_winsize_copies_source_size(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_install_winsize_forwarding_syncs_immediately_and_restores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sync_calls: list[tuple[int, int]] = []
    installed_handlers: list[tuple[int, object]] = []
    previous_handler = signal.SIG_IGN

    def fake_sync_pty_winsize(*, source_fd: int, target_fd: int) -> None:
        sync_calls.append((source_fd, target_fd))

    def fake_getsignal(signum: int) -> object:
        _ = signum
        return previous_handler

    def fake_signal(signum: int, handler: object) -> None:
        installed_handlers.append((signum, handler))

    monkeypatch.setattr(
        process,
        "_sync_pty_winsize",
        fake_sync_pty_winsize,
    )
    monkeypatch.setattr(process.signal, "getsignal", fake_getsignal)
    monkeypatch.setattr(process.signal, "signal", fake_signal)

    restore = process._install_winsize_forwarding(source_fd=20, target_fd=21)

    assert sync_calls == [(20, 21)]
    assert installed_handlers[0][0] == signal.SIGWINCH

    handler = installed_handlers[0][1]
    assert callable(handler)
    handler(signal.SIGWINCH, None)

    assert sync_calls == [(20, 21), (20, 21)]

    restore()

    assert installed_handlers[-1] == (signal.SIGWINCH, previous_handler)


def test_run_harness_process_fork_uses_new_chat_and_materialized_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    harness_registry = get_default_harness_registry()
    config = load_config(repo_root)
    codex_adapter = harness_registry.get_subprocess_harness(HarnessId.CODEX)
    request = LaunchRequest(
        model="gpt-5.4",
        harness="codex",
        session_mode=SessionMode.FORK,
        session=SessionRequest(
            requested_harness_session_id="source-session",
            continue_chat_id="c7",
            forked_from_chat_id="c7",
            continue_fork=True,
        ),
    )
    plan = ResolvedPrimaryLaunchPlan(
        repo_root=repo_root,
        state_root=tmp_path / ".meridian",
        prompt="fork prompt",
        request=request,
        config=config,
        adapter=codex_adapter,
        session_metadata=PrimarySessionMetadata(
            harness="codex",
            model="gpt-5.4",
            agent="",
            agent_path="",
            skills=(),
            skill_paths=(),
        ),
        run_params=SpawnParams(
            prompt="fork prompt",
            model=ModelId("gpt-5.4"),
            interactive=True,
            continue_harness_session_id="source-session",
            continue_fork=True,
        ),
        permission_config=PermissionConfig(),
        permission_resolver=TieredPermissionResolver(config=PermissionConfig()),
        command=("codex", "resume", "source-session"),
        seed_harness_session_id="source-session",
        command_request=request,
    )

    captured: dict[str, str | None] = {}

    def fake_build_command(run: SpawnParams, perms: object) -> list[str]:
        _ = perms
        captured["build_continue_session"] = run.continue_harness_session_id
        return ["codex", "resume", run.continue_harness_session_id or ""]

    def fake_fork_session(source_session_id: str) -> str:
        captured["fork_source_session"] = source_session_id
        return "forked-session"

    def fake_build_launch_env(*args: object, **kwargs: object) -> dict[str, str]:
        _ = args, kwargs
        return {}

    def fake_run_primary_process_with_capture(**kwargs: object) -> tuple[int, int]:
        captured["command_session"] = tuple(kwargs["command"])[2]
        started = kwargs.get("on_child_started")
        assert callable(started)
        started(111)
        return (0, 111)

    def fake_start_session(
        state_root: Path,
        harness: str,
        harness_session_id: str | None,
        model: str,
        chat_id: str | None = None,
        **kwargs: Any,
    ) -> str:
        _ = (state_root, harness, model)
        captured["chat_id_arg"] = chat_id
        captured["start_harness_session_id"] = harness_session_id
        captured["forked_from_chat_id"] = kwargs.get("forked_from_chat_id")
        return "c999"

    monkeypatch.setattr(codex_adapter, "build_command", fake_build_command)
    monkeypatch.setattr(codex_adapter, "fork_session", fake_fork_session)
    monkeypatch.setattr(codex_adapter, "observe_session_id", lambda **kwargs: "forked-session")
    monkeypatch.setattr(process, "build_launch_env", fake_build_launch_env)
    monkeypatch.setattr(
        process,
        "_run_primary_process_with_capture",
        fake_run_primary_process_with_capture,
    )
    monkeypatch.setattr(process, "stop_session", lambda *args, **kwargs: None)
    monkeypatch.setattr(process, "update_session_harness_id", lambda *args, **kwargs: None)
    monkeypatch.setattr(process, "start_session", fake_start_session)

    outcome = process.run_harness_process(plan, harness_registry)

    assert captured["fork_source_session"] == "source-session"
    assert captured["build_continue_session"] == "forked-session"
    assert captured["command_session"] == "forked-session"
    assert captured["chat_id_arg"] is None
    # I-10: session is created with the SOURCE session ID; fork happens after the row exists.
    assert captured["start_harness_session_id"] == "source-session"
    assert captured["forked_from_chat_id"] == "c7"
    assert outcome.chat_id == "c999"
    events = [
        json.loads(line)
        for line in (plan.state_root / "spawns.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    finalize_events = [event for event in events if event.get("event") == "finalize"]
    assert len(finalize_events) == 1
    assert finalize_events[0]["origin"] == "launcher"


def _build_spawn_request(
    prompt: str = "hello",
    extra_args: tuple[str, ...] = (),
) -> SpawnRequest:
    return SpawnRequest(
        model="gpt-5.4",
        harness=HarnessId.CODEX.value,
        prompt=prompt,
        extra_args=extra_args,
    )


def _build_launch_runtime(
    *,
    tmp_path: Path,
    override: str | None = None,
) -> LaunchRuntime:
    return LaunchRuntime(
        launch_mode="foreground",
        harness_command_override=override,
        report_output_path=(tmp_path / "report.md").as_posix(),
        state_root=(tmp_path / ".meridian").as_posix(),
        project_paths_repo_root=tmp_path.as_posix(),
        project_paths_execution_cwd=tmp_path.as_posix(),
    )


def test_build_launch_context_dry_run_runtime_share_same_argv_for_raw_request(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("MERIDIAN_HARNESS_COMMAND", raising=False)
    request = _build_spawn_request()
    runtime = _build_launch_runtime(tmp_path=tmp_path)
    registry = get_default_harness_registry()

    runtime_ctx = build_launch_context(
        spawn_id="p-ctx",
        request=request,
        runtime=runtime,
        harness_registry=registry,
        dry_run=False,
    )
    dry_run_ctx = build_launch_context(
        spawn_id="p-ctx",
        request=request,
        runtime=runtime,
        harness_registry=registry,
        dry_run=True,
    )

    assert runtime_ctx.argv == dry_run_ctx.argv
    assert runtime_ctx.is_bypass is False
    assert dry_run_ctx.is_bypass is False


def test_build_launch_context_bypass_command_owned_by_factory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("MERIDIAN_HARNESS_COMMAND", raising=False)
    request = _build_spawn_request(extra_args=("--json", "--verbose"))
    runtime = _build_launch_runtime(tmp_path=tmp_path, override="codex exec")
    registry = get_default_harness_registry()

    runtime_ctx = build_launch_context(
        spawn_id="p-ctx",
        request=request,
        runtime=runtime,
        harness_registry=registry,
        dry_run=False,
    )
    dry_run_ctx = build_launch_context(
        spawn_id="p-ctx",
        request=request,
        runtime=runtime,
        harness_registry=registry,
        dry_run=True,
    )

    assert runtime_ctx.is_bypass is True
    assert dry_run_ctx.is_bypass is True
    assert runtime_ctx.argv == ("codex", "exec", "--json", "--verbose")
    assert runtime_ctx.argv == dry_run_ctx.argv


def test_shared_runner_constants_defined_once() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    source_root = repo_root / "src"
    constants_path = source_root / "meridian/lib/launch/constants.py"

    patterns = {
        "DEFAULT_INFRA_EXIT_CODE": r"^DEFAULT_INFRA_EXIT_CODE\b.*=",
        "OUTPUT_FILENAME": r"^OUTPUT_FILENAME\b.*=",
        "STDERR_FILENAME": r"^STDERR_FILENAME\b.*=",
        "TOKENS_FILENAME": r"^TOKENS_FILENAME\b.*=",
        "REPORT_FILENAME": r"^REPORT_FILENAME\b.*=",
    }

    for name, pattern in patterns.items():
        matches: list[Path] = []
        for path in source_root.rglob("*.py"):
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if re.search(pattern, line):
                    matches.append(path)
                    break
        assert matches == [constants_path], f"{name} defined outside constants.py: {matches}"

    streaming_source = (
        source_root / "meridian/lib/launch/streaming_runner.py"
    ).read_text(encoding="utf-8")
    assert "DEFAULT_INFRA_EXIT_CODE =" not in streaming_source
    assert DEFAULT_INFRA_EXIT_CODE == 2
