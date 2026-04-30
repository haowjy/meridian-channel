from meridian.lib.chat.protocol import EVENT_FAMILIES, EVENT_FAMILY_RUNTIME, ChatEvent, utc_now_iso


def test_chat_event_payload_defaults_are_independent():
    first = ChatEvent("chat.started", 0, "c1", "e1", utc_now_iso())
    second = ChatEvent("chat.started", 1, "c1", "e1", utc_now_iso())

    first.payload["x"] = 1

    assert second.payload == {}


def test_event_families_include_runtime():
    assert EVENT_FAMILY_RUNTIME in EVENT_FAMILIES
