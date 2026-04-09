"""Headless runner for Phase-1 streaming spawn integration."""

from __future__ import annotations

import asyncio
import signal
from collections.abc import Iterable

from meridian.lib.core.types import HarnessId
from meridian.lib.harness.connections.base import ConnectionConfig, HarnessEvent
from meridian.lib.ops.runtime import resolve_runtime_root_and_config
from meridian.lib.state import spawn_store
from meridian.lib.state.paths import resolve_state_paths
from meridian.lib.streaming.spawn_manager import SpawnManager

_TERMINAL_EVENT_TYPES = frozenset(
    {
        "turn/completed",
        "turn.completed",
        "result",
        "done",
        "completed",
        "finished",
        "cancelled",
        "canceled",
    }
)
_NON_TERMINAL_EXACT = frozenset({"item.completed"})


def _is_terminal_event(event_type: str) -> bool:
    normalized = event_type.strip().lower()
    if not normalized:
        return False
    if normalized in _NON_TERMINAL_EXACT:
        return False
    if normalized in _TERMINAL_EVENT_TYPES:
        return True
    if "start" in normalized:
        return False
    terminal_tokens = (
        "complete",
        "completed",
        "done",
        "result",
        "finished",
        "cancelled",
        "canceled",
    )
    return any(token in normalized for token in terminal_tokens)


def _install_signal_handlers(
    loop: asyncio.AbstractEventLoop,
    shutdown_event: asyncio.Event,
) -> list[signal.Signals]:
    installed: list[signal.Signals] = []
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, shutdown_event.set)
            installed.append(sig)
        except (NotImplementedError, RuntimeError):
            continue
    return installed


def _remove_signal_handlers(
    loop: asyncio.AbstractEventLoop,
    signals: Iterable[signal.Signals],
) -> None:
    for sig in signals:
        try:
            loop.remove_signal_handler(sig)
        except Exception:
            continue


async def _wait_for_terminal_event(
    queue: asyncio.Queue[HarnessEvent | None],
) -> str:
    while True:
        event = await queue.get()
        if event is None:
            return "connection_closed"
        if _is_terminal_event(event.event_type):
            return event.event_type


async def _wait_for_shutdown(shutdown_event: asyncio.Event) -> str:
    await shutdown_event.wait()
    return "shutdown_requested"


async def streaming_serve(
    harness: str,
    prompt: str,
    model: str | None = None,
    agent: str | None = None,
) -> None:
    """Start a bidirectional spawn and keep it running until completion."""

    normalized_harness = harness.strip().lower()
    if not normalized_harness:
        raise ValueError("harness is required")

    try:
        harness_id = HarnessId(normalized_harness)
    except ValueError as exc:
        supported = ", ".join(item.value for item in HarnessId if item != HarnessId.DIRECT)
        raise ValueError(f"unsupported harness '{harness}'. Supported: {supported}") from exc

    repo_root, _ = resolve_runtime_root_and_config(None)
    state_paths = resolve_state_paths(repo_root)
    state_root = state_paths.root_dir
    spawn_id = spawn_store.next_spawn_id(state_root)

    manager = SpawnManager(state_root=state_root, repo_root=repo_root)
    config = ConnectionConfig(
        spawn_id=spawn_id,
        harness_id=harness_id,
        model=(model.strip() or None) if model is not None else None,
        agent=(agent.strip() or None) if agent is not None else None,
        prompt=prompt,
        repo_root=repo_root,
        env_overrides={},
    )

    output_path = state_root / "spawns" / str(spawn_id) / "output.jsonl"
    socket_path = state_root / "spawns" / str(spawn_id) / "control.sock"

    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()
    installed_signals = _install_signal_handlers(loop, shutdown_event)

    terminal_reason = "shutdown_requested"
    completion_task: asyncio.Task[str] | None = None
    shutdown_task: asyncio.Task[str] | None = None
    try:
        await manager.start_spawn(config)
        print(f"Started spawn {spawn_id} (harness={harness_id.value})")
        print(f"Control socket: {socket_path}")
        print(f"Events: {output_path}")

        subscriber = manager.subscribe(spawn_id)
        if subscriber is None:
            raise RuntimeError("failed to attach spawn event subscriber")

        completion_task = asyncio.create_task(_wait_for_terminal_event(subscriber))
        shutdown_task = asyncio.create_task(_wait_for_shutdown(shutdown_event))

        done, pending = await asyncio.wait(
            (completion_task, shutdown_task),
            return_when=asyncio.FIRST_COMPLETED,
        )
        for pending_task in pending:
            pending_task.cancel()

        terminal_reason = next(iter(done)).result()
    except KeyboardInterrupt:
        terminal_reason = "keyboard_interrupt"
    finally:
        if completion_task is not None and not completion_task.done():
            completion_task.cancel()
        if shutdown_task is not None and not shutdown_task.done():
            shutdown_task.cancel()
        manager.unsubscribe(spawn_id)
        _remove_signal_handlers(loop, installed_signals)
        await manager.shutdown()
        print(f"Stopped spawn {spawn_id} ({terminal_reason})")
