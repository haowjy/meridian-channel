import json

from meridian.lib.chat.event_log import ChatEventLog
from meridian.lib.chat.protocol import ChatEvent, utc_now_iso


def _event(chat_id="c1", event_type="turn.started"):
    return ChatEvent(event_type, 999, chat_id, "e1", utc_now_iso(), payload={"k": "v"})


def test_append_assigns_monotonic_seq(tmp_path):
    log = ChatEventLog(tmp_path / "events.jsonl")

    first = log.append(_event())
    second = log.append(_event())

    assert first.seq == 0
    assert second.seq == 1
    assert [event.seq for event in log.read_all()] == [0, 1]


def test_recover_seq_ignores_truncated_tail(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text(
        json.dumps({
            "type": "turn.started",
            "seq": 0,
            "chat_id": "c1",
            "execution_id": "e1",
            "timestamp": utc_now_iso(),
            "turn_id": None,
            "item_id": None,
            "request_id": None,
            "payload": {},
            "harness_id": None,
        })
        + "\n"
        + '{"type":',
        encoding="utf-8",
    )

    log = ChatEventLog(path)
    appended = log.append(_event())

    assert appended.seq == 1
    assert [event.seq for event in log.read_all()] == [0, 1]


def test_read_from_filters_by_seq(tmp_path):
    log = ChatEventLog(tmp_path / "events.jsonl")
    log.append(_event())
    log.append(_event())

    assert [event.seq for event in log.read_from(1)] == [1]
