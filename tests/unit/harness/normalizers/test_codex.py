from meridian.lib.harness.connections.base import HarnessEvent
from meridian.lib.harness.normalizers.codex import CodexNormalizer


def event(event_type, payload):
    return HarnessEvent(event_type=event_type, payload=payload, harness_id="codex")


def test_codex_text_sequence_normalizes_turn_content_and_usage():
    n = CodexNormalizer("c1", "s1")

    started = n.normalize(event("turn/started", {"turn_id": "t1", "model": "gpt"}))[0]
    delta = n.normalize(event("agent_message_chunk", {"text": "hi"}))[0]
    completed = n.normalize(event("turn/completed", {"usage": {"input_tokens": 1}}))[0]

    assert started.type == "turn.started"
    assert started.turn_id == "t1"
    assert delta.type == "content.delta"
    assert delta.turn_id == "t1"
    assert delta.payload == {"stream_kind": "assistant_text", "text": "hi"}
    assert completed.type == "turn.completed"
    assert completed.payload["usage"] == {"input_tokens": 1}


def test_codex_item_lifecycle_and_files_persisted():
    n = CodexNormalizer("c1", "s1")
    n.normalize(event("turn/started", {"turn_id": "t1"}))

    started = n.normalize(
        event("item/tool/started", {"item": {"id": "i1", "type": "bash", "name": "shell"}})
    )[0]
    updated = n.normalize(event("item/tool/updated", {"item_id": "i1", "delta": "running"}))[0]
    completed, files = n.normalize(
        event("item/tool/completed", {"item_id": "i1", "path": "a.txt", "operation": "write"})
    )

    assert started.type == "item.started"
    assert started.payload["item_type"] == "command_execution"
    assert updated.type == "item.updated"
    assert completed.type == "item.completed"
    assert files.type == "files.persisted"
    assert files.payload == {"files": [{"path": "a.txt", "operation": "write"}]}


def test_codex_reasoning_requests_synthetic_boundary_and_unknowns():
    n = CodexNormalizer("c1", "s1")
    reasoning = n.normalize(event("agent_thought_chunk", {"text": "hmm"}))[0]
    opened = n.normalize(
        event("request.opened", {"request_id": "r1", "request_type": "approval"})
    )[0]
    user_input = n.normalize(event("user_input.requested", {"request_id": "r2"}))[0]
    synthetic = n.normalize(
        event("meridian/turn_completed", {"status": "succeeded", "synthetic": True})
    )[0]

    assert reasoning.payload == {"stream_kind": "reasoning_text", "text": "hmm"}
    assert opened.type == "request.opened"
    assert opened.request_id == "r1"
    assert user_input.type == "user_input.requested"
    assert user_input.payload["request_type"] == "user_input"
    assert synthetic.type == "turn.completed"
    assert synthetic.payload["synthetic"] is True
    assert n.normalize(event("surprise", {})) == []
