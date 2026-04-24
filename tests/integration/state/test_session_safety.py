from __future__ import annotations

import json
import multiprocessing
import sys
from pathlib import Path
from typing import Any

import pytest

from meridian.lib.state import session_store


def _spawn_queue_or_skip() -> tuple[Any, multiprocessing.Queue[Any]]:
    ctx = multiprocessing.get_context("spawn")
    try:
        queue: multiprocessing.Queue[Any] = ctx.Queue()
    except PermissionError as exc:
        pytest.skip(f"multiprocessing semaphore unavailable in this environment: {exc}")
    return ctx, queue


def _start_process_or_skip(proc: Any) -> None:
    try:
        proc.start()
    except PermissionError as exc:
        pytest.skip(f"multiprocessing semaphore unavailable in this environment: {exc}")


def _state_root(tmp_path: Path) -> Path:
    state_dir = tmp_path / ".meridian"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def _reserve_chat_id_worker(state_root_str: str, queue: multiprocessing.Queue[str]) -> None:
    runtime_root = Path(state_root_str)
    queue.put(session_store.reserve_chat_id(runtime_root))


def _can_acquire_lock_nonblocking_worker(
    lock_path_str: str, queue: multiprocessing.Queue[bool]
) -> None:
    lock_path = Path(lock_path_str)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        locked = session_store._try_lock_nonblocking(handle)
        if not locked:
            queue.put(False)
            return
        session_store._release_session_lock_handle(handle)
        queue.put(True)


def _write_session_start(
    *,
    runtime_root: Path,
    chat_id: str,
    session_instance_id: str,
    harness: str = "codex",
    kind: str = "spawn",
) -> None:
    with (runtime_root / "sessions.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "v": 1,
                    "event": "start",
                    "chat_id": chat_id,
                    "kind": kind,
                    "harness": harness,
                    "harness_session_id": f"{chat_id}-thread",
                    "model": "gpt-5.4",
                    "session_instance_id": session_instance_id,
                    "started_at": "2026-03-01T00:00:00Z",
                },
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        )


def test_reserve_chat_id_is_safe_under_concurrency(tmp_path: Path) -> None:
    runtime_root = _state_root(tmp_path)

    process_count = 8
    ctx, queue = _spawn_queue_or_skip()
    procs = [
        ctx.Process(
            target=_reserve_chat_id_worker,
            args=(runtime_root.as_posix(), queue),
        )
        for _ in range(process_count)
    ]
    for proc in procs:
        _start_process_or_skip(proc)
    for proc in procs:
        proc.join(timeout=20)
        assert proc.exitcode == 0

    allocated = sorted(queue.get(timeout=5) for _ in range(process_count))
    assert allocated == [f"c{idx}" for idx in range(1, process_count + 1)]
    assert (runtime_root / "session-id-counter").read_text(encoding="utf-8") == f"{process_count}\n"


def test_start_session_does_not_append_start_event_when_lock_acquire_fails(
    tmp_path: Path,
) -> None:
    runtime_root = _state_root(tmp_path)
    sessions_dir_as_file = runtime_root / "sessions"
    sessions_dir_as_file.write_text("not-a-directory\n", encoding="utf-8")

    with pytest.raises(OSError):
        session_store.start_session(
            runtime_root,
            harness="codex",
            harness_session_id="thread-1",
            model="gpt-5.4",
        )

    assert not (runtime_root / "sessions.jsonl").exists()


@pytest.mark.parametrize(
    (
        "chat_id",
        "harness",
        "start_generation",
        "lease_generation",
        "expected_cleaned",
        "expected_materialized",
        "expect_lock_exists",
        "expect_lease_exists",
        "expected_stop_count",
    ),
    [
        pytest.param(
            "c7",
            "codex",
            "new-generation",
            "old-generation",
            (),
            (),
            True,
            True,
            0,
            id="skips-generation-mismatch",
        ),
        pytest.param(
            "c8",
            "claude",
            "matching-generation",
            "matching-generation",
            ("c8",),
            ("claude",),
            False,
            False,
            1,
            id="stops-and-cleans-when-generation-matches",
        ),
    ],
)
def test_cleanup_stale_sessions_handles_generation_rules(
    tmp_path: Path,
    chat_id: str,
    harness: str,
    start_generation: str,
    lease_generation: str,
    expected_cleaned: tuple[str, ...],
    expected_materialized: tuple[str, ...],
    expect_lock_exists: bool,
    expect_lease_exists: bool,
    expected_stop_count: int,
) -> None:
    runtime_root = _state_root(tmp_path)
    _write_session_start(
        runtime_root=runtime_root,
        chat_id=chat_id,
        session_instance_id=start_generation,
        harness=harness,
    )

    lock_path = runtime_root / "sessions" / f"{chat_id}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch()
    lease_path = runtime_root / "sessions" / f"{chat_id}.lease.json"
    lease_path.write_text(
        json.dumps(
            {
                "chat_id": chat_id,
                "owner_pid": 123,
                "session_instance_id": lease_generation,
            }
        ),
        encoding="utf-8",
    )

    cleanup = session_store.cleanup_stale_sessions(runtime_root)

    assert cleanup.cleaned_ids == expected_cleaned
    assert cleanup.materialized_scopes == expected_materialized
    assert lock_path.exists() is expect_lock_exists
    assert lease_path.exists() is expect_lease_exists

    rows = [
        json.loads(line)
        for line in (runtime_root / "sessions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    stop_rows = [
        row for row in rows if row.get("event") == "stop" and row.get("chat_id") == chat_id
    ]
    assert len(stop_rows) == expected_stop_count
    if expected_stop_count == 1:
        assert stop_rows[0]["session_instance_id"] == start_generation


def test_cleanup_stale_primary_session_with_dead_pid_is_cleaned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = _state_root(tmp_path)
    chat_id = "c9"
    session_generation = "primary-generation"
    _write_session_start(
        runtime_root=runtime_root,
        chat_id=chat_id,
        session_instance_id=session_generation,
        harness="claude",
        kind="primary",
    )

    lock_path = runtime_root / "sessions" / f"{chat_id}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch()
    lease_path = runtime_root / "sessions" / f"{chat_id}.lease.json"
    lease_path.write_text(
        json.dumps(
            {
                "chat_id": chat_id,
                "owner_pid": 43210,
                "session_instance_id": session_generation,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(session_store, "is_process_alive", lambda _pid: False)

    cleanup = session_store.cleanup_stale_sessions(runtime_root)
    assert cleanup.cleaned_ids == (chat_id,)
    assert cleanup.materialized_scopes == ("claude",)
    assert not lock_path.exists()
    assert not lease_path.exists()

    rows = [
        json.loads(line)
        for line in (runtime_root / "sessions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    stop_rows = [
        row for row in rows if row.get("event") == "stop" and row.get("chat_id") == chat_id
    ]
    assert len(stop_rows) == 1
    assert stop_rows[0]["session_instance_id"] == session_generation


def test_cleanup_stale_primary_session_with_live_pid_is_not_cleaned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = _state_root(tmp_path)
    chat_id = "c10"
    session_generation = "primary-generation"
    _write_session_start(
        runtime_root=runtime_root,
        chat_id=chat_id,
        session_instance_id=session_generation,
        harness="claude",
        kind="primary",
    )

    lock_path = runtime_root / "sessions" / f"{chat_id}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch()
    lease_path = runtime_root / "sessions" / f"{chat_id}.lease.json"
    lease_path.write_text(
        json.dumps(
            {
                "chat_id": chat_id,
                "owner_pid": 54321,
                "session_instance_id": session_generation,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(session_store, "is_process_alive", lambda _pid: True)

    cleanup = session_store.cleanup_stale_sessions(runtime_root)
    assert cleanup.cleaned_ids == ()
    assert cleanup.materialized_scopes == ()
    assert lock_path.exists()
    assert lease_path.exists()

    rows = [
        json.loads(line)
        for line in (runtime_root / "sessions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    stop_rows = [
        row for row in rows if row.get("event") == "stop" and row.get("chat_id") == chat_id
    ]
    assert stop_rows == []


@pytest.mark.skipif(sys.platform == "win32", reason="fcntl not available")
def test_acquire_session_lock_retries_when_lock_file_is_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = _state_root(tmp_path)
    lock_path = runtime_root / "sessions" / "c123.lock"
    real_flock = session_store.fcntl.flock
    observed = {"lock_ex_calls": 0, "replaced": False}

    def _flock_with_unlink(fd: int, operation: int) -> None:
        if operation == session_store.fcntl.LOCK_EX:
            observed["lock_ex_calls"] += 1
            if not observed["replaced"]:
                observed["replaced"] = True
                lock_path.unlink(missing_ok=True)
                lock_path.touch()
        real_flock(fd, operation)

    monkeypatch.setattr(session_store.fcntl, "flock", _flock_with_unlink)

    chat_id = session_store.start_session(
        runtime_root,
        harness="codex",
        harness_session_id="thread-replaced",
        model="gpt-5.4",
        chat_id="c123",
    )
    try:
        assert chat_id == "c123"
        assert observed["replaced"] is True
        assert observed["lock_ex_calls"] >= 2

        ctx, queue = _spawn_queue_or_skip()
        proc = ctx.Process(
            target=_can_acquire_lock_nonblocking_worker,
            args=(lock_path.as_posix(), queue),
        )
        _start_process_or_skip(proc)
        proc.join(timeout=20)
        assert proc.exitcode == 0
        assert queue.get(timeout=5) is False
    finally:
        session_store.stop_session(runtime_root, chat_id)


def test_start_session_acquires_lifetime_lock_before_appending_start_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = _state_root(tmp_path)
    original_append_event = session_store.append_event
    observed = {"checked": False}

    def _append_event_with_lock_check(*args: object, **kwargs: object) -> None:
        event = kwargs.get("event")
        if event is None and len(args) >= 3:
            event = args[2]
        if isinstance(event, session_store.SessionStartEvent):
            ctx, queue = _spawn_queue_or_skip()
            lock_path = runtime_root / "sessions" / f"{event.chat_id}.lock"
            proc = ctx.Process(
                target=_can_acquire_lock_nonblocking_worker,
                args=(lock_path.as_posix(), queue),
            )
            _start_process_or_skip(proc)
            proc.join(timeout=20)
            assert proc.exitcode == 0
            assert queue.get(timeout=5) is False
            observed["checked"] = True
        original_append_event(*args, **kwargs)

    monkeypatch.setattr(session_store, "append_event", _append_event_with_lock_check)

    chat_id = session_store.start_session(
        runtime_root,
        harness="codex",
        harness_session_id="thread-ordered",
        model="gpt-5.4",
    )
    assert observed["checked"] is True

    session_store.stop_session(runtime_root, chat_id)


def test_start_session_rolls_back_lock_and_event_on_append_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = _state_root(tmp_path)
    chat_id = "c99"

    def _raise_append_error(*_: object, **__: object) -> None:
        raise RuntimeError("append failed")

    monkeypatch.setattr(session_store, "append_event", _raise_append_error)

    with pytest.raises(RuntimeError, match="append failed"):
        session_store.start_session(
            runtime_root,
            harness="codex",
            harness_session_id="thread-fail",
            model="gpt-5.4",
            chat_id=chat_id,
        )

    assert not (runtime_root / "sessions.jsonl").exists()
    assert not (runtime_root / "sessions" / f"{chat_id}.lease.json").exists()
    assert (
        session_store._session_lock_key(runtime_root, chat_id)
        not in session_store._SESSION_LOCK_HANDLES
    )

    ctx, queue = _spawn_queue_or_skip()
    lock_path = runtime_root / "sessions" / f"{chat_id}.lock"
    proc = ctx.Process(
        target=_can_acquire_lock_nonblocking_worker,
        args=(lock_path.as_posix(), queue),
    )
    _start_process_or_skip(proc)
    proc.join(timeout=20)
    assert proc.exitcode == 0
    assert queue.get(timeout=5) is True


def test_records_by_session_ignores_mismatched_generation_stop_and_update(tmp_path: Path) -> None:
    runtime_root = _state_root(tmp_path)
    with (runtime_root / "sessions.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "v": 1,
                    "event": "start",
                    "chat_id": "c10",
                    "harness": "codex",
                    "harness_session_id": "thread-1",
                    "model": "gpt-5.4",
                    "session_instance_id": "gen-a",
                    "started_at": "2026-03-01T00:00:00Z",
                },
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        )
        handle.write(
            json.dumps(
                {
                    "v": 1,
                    "event": "update",
                    "chat_id": "c10",
                    "harness_session_id": "thread-2",
                    "session_instance_id": "gen-a",
                    "active_work_id": "work-1",
                },
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        )
        handle.write(
            json.dumps(
                {
                    "v": 1,
                    "event": "update",
                    "chat_id": "c10",
                    "harness_session_id": "thread-ignored",
                    "session_instance_id": "gen-b",
                    "active_work_id": "work-ignored",
                },
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        )
        handle.write(
            json.dumps(
                {
                    "v": 1,
                    "event": "stop",
                    "chat_id": "c10",
                    "session_instance_id": "gen-b",
                    "stopped_at": "2026-03-01T00:01:00Z",
                },
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        )

    record = session_store._records_by_session(runtime_root)["c10"]
    assert record.harness_session_id == "thread-2"
    assert record.harness_session_ids == ("thread-1", "thread-2")
    assert record.active_work_id == "work-1"
    assert record.forked_from_chat_id is None
    assert record.stopped_at is None


def test_empty_harness_session_id_flows_through_start_update_and_record(tmp_path: Path) -> None:
    runtime_root = _state_root(tmp_path)
    chat_id = session_store.start_session(
        runtime_root,
        harness="opencode",
        harness_session_id="",
        model="opencode-gpt-5.3-codex",
        chat_id="c42",
    )
    try:
        session_store.update_session_harness_id(runtime_root, chat_id, "resolved-thread")

        record = session_store.get_session_record(runtime_root, chat_id)
        assert record is not None
        assert record.harness_session_id == "resolved-thread"
        assert record.harness_session_ids == ("", "resolved-thread")

        rows = [
            json.loads(line)
            for line in (runtime_root / "sessions.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert rows[0]["event"] == "start"
        assert rows[0]["harness_session_id"] == ""
        assert rows[1]["event"] == "update"
        assert rows[1]["harness_session_id"] == "resolved-thread"
    finally:
        session_store.stop_session(runtime_root, chat_id)


def test_list_all_session_records_includes_stopped_sessions(tmp_path: Path) -> None:
    runtime_root = _state_root(tmp_path)
    stopped_chat_id = session_store.start_session(
        runtime_root,
        harness="codex",
        harness_session_id="thread-stopped",
        model="gpt-5.4",
        chat_id="c1",
    )
    active_chat_id = session_store.start_session(
        runtime_root,
        harness="codex",
        harness_session_id="thread-active",
        model="gpt-5.4",
        chat_id="c2",
    )
    try:
        session_store.stop_session(runtime_root, stopped_chat_id)
        records = session_store.list_all_session_records(runtime_root)
        by_chat_id = {record.chat_id: record for record in records}
        assert set(by_chat_id) == {stopped_chat_id, active_chat_id}
        assert by_chat_id[stopped_chat_id].stopped_at is not None
        assert by_chat_id[active_chat_id].stopped_at is None
    finally:
        session_store.stop_session(runtime_root, active_chat_id)


def test_get_session_record_returns_record_or_none(tmp_path: Path) -> None:
    runtime_root = _state_root(tmp_path)
    assert session_store.get_session_record(runtime_root, "missing") is None

    chat_id = session_store.start_session(
        runtime_root,
        harness="codex",
        harness_session_id="thread-lookup",
        model="gpt-5.4",
        chat_id="c3",
    )
    try:
        record = session_store.get_session_record(runtime_root, chat_id)
        assert record is not None
        assert record.chat_id == chat_id
        assert record.harness_session_id == "thread-lookup"
    finally:
        session_store.stop_session(runtime_root, chat_id)
