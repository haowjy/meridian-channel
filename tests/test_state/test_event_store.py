import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterator

import pytest

from pydantic import BaseModel

from meridian.lib.state.event_store import (
    append_event,
    lock_file,
    read_events,
    register_observer,
    unregister_observer,
    utc_now_iso,
)


class _ReadEvent(BaseModel):
    id: int
    kind: str


class _AppendEvent(BaseModel):
    z_key: str
    a_key: str
    optional: str | None = None


def _parse_read_event(payload: dict[str, Any]) -> _ReadEvent:
    return _ReadEvent.model_validate(payload)


def _write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("".join(lines), encoding="utf-8")


def test_utc_now_iso_returns_z_and_no_microseconds() -> None:
    iso = utc_now_iso()

    assert iso.endswith("Z")
    parsed = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    assert parsed.microsecond == 0


def test_read_events_skips_truncated_trailing_line(tmp_path: Path) -> None:
    data_path = tmp_path / "events.jsonl"
    _write_lines(
        data_path,
        [
            '{"id":1,"kind":"start"}\n',
            '{"id":2,"kind":"update"}\n',
            '{"id":3,"kind":"broken"',
        ],
    )

    rows = read_events(data_path, _parse_read_event)

    assert [row.id for row in rows] == [1, 2]


def test_read_events_skips_malformed_json_in_middle(tmp_path: Path) -> None:
    data_path = tmp_path / "events.jsonl"
    _write_lines(
        data_path,
        [
            '{"id":1,"kind":"start"}\n',
            "{not-valid-json}\n",
            '{"id":2,"kind":"done"}\n',
        ],
    )

    rows = read_events(data_path, _parse_read_event)

    assert [row.id for row in rows] == [1, 2]


def test_read_events_skips_validation_errors_from_parser(tmp_path: Path) -> None:
    data_path = tmp_path / "events.jsonl"
    _write_lines(
        data_path,
        [
            '{"id":1,"kind":"start"}\n',
            '{"id":"bad","kind":"update"}\n',
            '{"id":2,"kind":"done"}\n',
        ],
    )

    rows = read_events(data_path, _parse_read_event)

    assert [row.id for row in rows] == [1, 2]


def test_read_events_returns_empty_for_empty_file(tmp_path: Path) -> None:
    data_path = tmp_path / "events.jsonl"
    data_path.write_text("", encoding="utf-8")

    assert read_events(data_path, _parse_read_event) == []


def test_read_events_returns_empty_for_blank_lines_only(tmp_path: Path) -> None:
    data_path = tmp_path / "events.jsonl"
    data_path.write_text("\n  \n\t\n", encoding="utf-8")

    assert read_events(data_path, _parse_read_event) == []


def test_read_events_returns_empty_when_file_missing(tmp_path: Path) -> None:
    data_path = tmp_path / "missing.jsonl"

    assert read_events(data_path, _parse_read_event) == []


def test_read_events_handles_many_lines(tmp_path: Path) -> None:
    data_path = tmp_path / "many.jsonl"
    lines = [json.dumps({"id": i, "kind": "tick"}, separators=(",", ":")) + "\n" for i in range(150)]
    _write_lines(data_path, lines)

    rows = read_events(data_path, _parse_read_event)

    assert len(rows) == 150
    assert rows[0].id == 0
    assert rows[-1].id == 149


def test_append_event_writes_single_compact_sorted_jsonl_line(tmp_path: Path) -> None:
    data_path = tmp_path / "events.jsonl"
    lock_path = tmp_path / "events.lock"
    event = _AppendEvent(z_key="z", a_key="a", optional=None)

    append_event(data_path, lock_path, event, store_name="test", exclude_none=False)

    assert data_path.read_text(encoding="utf-8") == '{"a_key":"a","optional":null,"z_key":"z"}\n'


def test_append_event_exclude_none_true_omits_none_fields(tmp_path: Path) -> None:
    data_path = tmp_path / "events.jsonl"
    lock_path = tmp_path / "events.lock"
    event = _AppendEvent(z_key="z", a_key="a", optional=None)

    append_event(data_path, lock_path, event, store_name="test", exclude_none=True)

    assert data_path.read_text(encoding="utf-8") == '{"a_key":"a","z_key":"z"}\n'


def test_append_event_exclude_none_false_includes_none_fields(tmp_path: Path) -> None:
    data_path = tmp_path / "events.jsonl"
    lock_path = tmp_path / "events.lock"
    event = _AppendEvent(z_key="z", a_key="a", optional=None)

    append_event(data_path, lock_path, event, store_name="test", exclude_none=False)

    assert '"optional":null' in data_path.read_text(encoding="utf-8")


def test_append_event_multiple_appends_create_multiple_lines(tmp_path: Path) -> None:
    data_path = tmp_path / "events.jsonl"
    lock_path = tmp_path / "events.lock"

    append_event(
        data_path,
        lock_path,
        _AppendEvent(z_key="z1", a_key="a1", optional=None),
        store_name="test",
        exclude_none=True,
    )
    append_event(
        data_path,
        lock_path,
        _AppendEvent(z_key="z2", a_key="a2", optional=None),
        store_name="test",
        exclude_none=True,
    )

    lines = data_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert lines[0] == '{"a_key":"a1","z_key":"z1"}'
    assert lines[1] == '{"a_key":"a2","z_key":"z2"}'


def test_lock_file_can_acquire_release_and_reacquire(tmp_path: Path) -> None:
    lock_path = tmp_path / "events.lock"

    with lock_file(lock_path) as handle:
        assert not handle.closed

    assert handle.closed

    with lock_file(lock_path) as reacquired:
        assert not reacquired.closed


def test_lock_file_is_reentrant_in_same_thread(tmp_path: Path) -> None:
    lock_path = tmp_path / "events.lock"

    with lock_file(lock_path) as outer:
        with lock_file(lock_path) as inner:
            assert inner is outer
            assert not inner.closed
        assert not outer.closed

    assert outer.closed
    with lock_file(lock_path):
        pass


@pytest.fixture
def managed_observers() -> Iterator[
    Callable[[Callable[[str, dict[str, Any]], None]], Callable[[str, dict[str, Any]], None]]
]:
    observers: list[Callable[[str, dict[str, Any]], None]] = []

    def _register(observer: Callable[[str, dict[str, Any]], None]) -> Callable[[str, dict[str, Any]], None]:
        register_observer(observer)
        observers.append(observer)
        return observer

    try:
        yield _register
    finally:
        for observer in reversed(observers):
            unregister_observer(observer)


class TestEventStoreObservers:
    def test_observer_receives_notification_on_append(
        self,
        tmp_path: Path,
        managed_observers: Callable[[Callable[[str, dict[str, Any]], None]], Callable[[str, dict[str, Any]], None]],
    ) -> None:
        data_path = tmp_path / "events.jsonl"
        lock_path = tmp_path / "events.lock"
        event = _AppendEvent(z_key="z", a_key="a", optional=None)
        calls: list[tuple[str, dict[str, Any]]] = []

        def observer(store_name: str, payload: dict[str, Any]) -> None:
            calls.append((store_name, payload))

        managed_observers(observer)
        append_event(data_path, lock_path, event, store_name="observer-store", exclude_none=False)

        assert calls == [("observer-store", event.model_dump(exclude_none=False))]

    def test_multiple_observers_all_receive_notification(
        self,
        tmp_path: Path,
        managed_observers: Callable[[Callable[[str, dict[str, Any]], None]], Callable[[str, dict[str, Any]], None]],
    ) -> None:
        data_path = tmp_path / "events.jsonl"
        lock_path = tmp_path / "events.lock"
        event = _AppendEvent(z_key="z", a_key="a", optional=None)
        calls_a: list[tuple[str, dict[str, Any]]] = []
        calls_b: list[tuple[str, dict[str, Any]]] = []
        calls_c: list[tuple[str, dict[str, Any]]] = []

        managed_observers(lambda store_name, payload: calls_a.append((store_name, payload)))
        managed_observers(lambda store_name, payload: calls_b.append((store_name, payload)))
        managed_observers(lambda store_name, payload: calls_c.append((store_name, payload)))

        append_event(data_path, lock_path, event, store_name="observer-store", exclude_none=True)

        expected = [("observer-store", event.model_dump(exclude_none=True))]
        assert calls_a == expected
        assert calls_b == expected
        assert calls_c == expected

    def test_observer_receives_correct_payload(
        self,
        tmp_path: Path,
        managed_observers: Callable[[Callable[[str, dict[str, Any]], None]], Callable[[str, dict[str, Any]], None]],
    ) -> None:
        data_path = tmp_path / "events.jsonl"
        lock_path = tmp_path / "events.lock"
        event = _AppendEvent(z_key="z", a_key="a", optional=None)
        payloads: list[dict[str, Any]] = []

        managed_observers(lambda _store_name, payload: payloads.append(payload))
        append_event(data_path, lock_path, event, store_name="observer-store", exclude_none=True)

        assert payloads == [event.model_dump(exclude_none=True)]

    def test_observer_fires_after_durable_write(
        self,
        tmp_path: Path,
        managed_observers: Callable[[Callable[[str, dict[str, Any]], None]], Callable[[str, dict[str, Any]], None]],
    ) -> None:
        data_path = tmp_path / "events.jsonl"
        lock_path = tmp_path / "events.lock"
        event = _AppendEvent(z_key="z", a_key="a", optional=None)
        seen_file_contents: list[str] = []

        def observer(_store_name: str, _payload: dict[str, Any]) -> None:
            seen_file_contents.append(data_path.read_text(encoding="utf-8"))

        managed_observers(observer)
        append_event(data_path, lock_path, event, store_name="observer-store", exclude_none=True)

        expected_line = json.dumps(event.model_dump(exclude_none=True), separators=(",", ":"), sort_keys=True) + "\n"
        assert seen_file_contents == [expected_line]

    def test_observer_fires_outside_lock(
        self,
        tmp_path: Path,
        managed_observers: Callable[[Callable[[str, dict[str, Any]], None]], Callable[[str, dict[str, Any]], None]],
    ) -> None:
        data_path = tmp_path / "events.jsonl"
        lock_path = tmp_path / "events.lock"
        event = _AppendEvent(z_key="z", a_key="a", optional=None)
        lock_handle_closed_after_observer_lock: list[bool] = []

        def observer(_store_name: str, _payload: dict[str, Any]) -> None:
            with lock_file(lock_path) as handle:
                assert not handle.closed
            lock_handle_closed_after_observer_lock.append(handle.closed)

        managed_observers(observer)
        append_event(data_path, lock_path, event, store_name="observer-store", exclude_none=True)

        assert lock_handle_closed_after_observer_lock == [True]

    def test_observer_exception_does_not_propagate(
        self,
        tmp_path: Path,
        managed_observers: Callable[[Callable[[str, dict[str, Any]], None]], Callable[[str, dict[str, Any]], None]],
    ) -> None:
        data_path = tmp_path / "events.jsonl"
        lock_path = tmp_path / "events.lock"
        event = _AppendEvent(z_key="z", a_key="a", optional=None)

        def observer_raises(_store_name: str, _payload: dict[str, Any]) -> None:
            raise RuntimeError("observer failed")

        managed_observers(observer_raises)
        append_event(data_path, lock_path, event, store_name="observer-store", exclude_none=True)

        assert data_path.read_text(encoding="utf-8") == '{"a_key":"a","z_key":"z"}\n'

    def test_observer_exception_does_not_block_other_observers(
        self,
        tmp_path: Path,
        managed_observers: Callable[[Callable[[str, dict[str, Any]], None]], Callable[[str, dict[str, Any]], None]],
    ) -> None:
        data_path = tmp_path / "events.jsonl"
        lock_path = tmp_path / "events.lock"
        event = _AppendEvent(z_key="z", a_key="a", optional=None)
        successful_calls: list[tuple[str, dict[str, Any]]] = []

        def observer_raises(_store_name: str, _payload: dict[str, Any]) -> None:
            raise RuntimeError("observer failed")

        def observer_records(store_name: str, payload: dict[str, Any]) -> None:
            successful_calls.append((store_name, payload))

        managed_observers(observer_raises)
        managed_observers(observer_records)
        append_event(data_path, lock_path, event, store_name="observer-store", exclude_none=False)

        assert successful_calls == [("observer-store", event.model_dump(exclude_none=False))]

    def test_unregister_observer_removes_observer(
        self,
        tmp_path: Path,
        managed_observers: Callable[[Callable[[str, dict[str, Any]], None]], Callable[[str, dict[str, Any]], None]],
    ) -> None:
        data_path = tmp_path / "events.jsonl"
        lock_path = tmp_path / "events.lock"
        event = _AppendEvent(z_key="z", a_key="a", optional=None)
        calls: list[tuple[str, dict[str, Any]]] = []

        def observer(store_name: str, payload: dict[str, Any]) -> None:
            calls.append((store_name, payload))

        managed_observers(observer)
        unregister_observer(observer)
        append_event(data_path, lock_path, event, store_name="observer-store", exclude_none=True)

        assert calls == []

    def test_unregister_observer_is_safe_for_unregistered_observer(self) -> None:
        def never_registered(_store_name: str, _payload: dict[str, Any]) -> None:
            return

        unregister_observer(never_registered)

    def test_observer_receives_store_name(
        self,
        tmp_path: Path,
        managed_observers: Callable[[Callable[[str, dict[str, Any]], None]], Callable[[str, dict[str, Any]], None]],
    ) -> None:
        data_path = tmp_path / "events.jsonl"
        lock_path = tmp_path / "events.lock"
        event = _AppendEvent(z_key="z", a_key="a", optional=None)
        store_names: list[str] = []

        managed_observers(lambda store_name, _payload: store_names.append(store_name))
        append_event(data_path, lock_path, event, store_name="phase-2b-store-name", exclude_none=True)

        assert store_names == ["phase-2b-store-name"]
