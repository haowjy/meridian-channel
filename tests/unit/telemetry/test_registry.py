from __future__ import annotations

from meridian.lib.telemetry import (
    EVENT_REGISTRY,
    TelemetryEnvelope,
    concerns_for_event,
    make_error_data,
)
from meridian.lib.telemetry.events import VALID_CONCERNS, VALID_DOMAINS, validate_event


def test_registered_events_have_valid_domains_and_concerns() -> None:
    assert EVENT_REGISTRY
    for event, definition in EVENT_REGISTRY.items():
        assert event
        assert definition["domain"] in VALID_DOMAINS
        assert definition["concerns"]
        assert set(definition["concerns"]).issubset(VALID_CONCERNS)


def test_concern_tag_lookup_for_known_events() -> None:
    assert concerns_for_event("spawn.failed") == ("operational", "error")
    assert concerns_for_event("usage.command.invoked") == ("usage",)


def test_envelope_to_dict_omits_none_optional_fields() -> None:
    envelope = TelemetryEnvelope(
        v=1,
        ts="2026-05-02T12:00:00Z",
        domain="chat",
        event="chat.ws.connected",
        scope="chat.server.ws",
    )
    assert envelope.to_dict() == {
        "v": 1,
        "ts": "2026-05-02T12:00:00Z",
        "domain": "chat",
        "event": "chat.ws.connected",
        "scope": "chat.server.ws",
    }


def test_validate_event_rejects_invalid_domain_pair() -> None:
    validate_event("spawn", "spawn.failed", "error")
    try:
        validate_event("chat", "spawn.failed", "error")
    except ValueError as exc:
        assert "belongs to domain" in str(exc)
    else:
        raise AssertionError("expected invalid event/domain pair to fail")


def test_make_error_data_shape() -> None:
    exc = RuntimeError("boom")
    data = make_error_data(exc)
    assert data["error"]["type"] == "RuntimeError"
    assert data["error"]["message"] == "boom"
    assert "RuntimeError: boom" in data["error"]["stack"]
    assert make_error_data(message="plain") == {"error": {"message": "plain"}}
