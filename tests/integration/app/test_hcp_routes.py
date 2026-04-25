from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from meridian.lib.app.agui_replay import PaginationCursor, encode_pagination_cursor
from meridian.lib.app.hcp_routes import register_hcp_routes
from meridian.lib.config.project_paths import resolve_project_config_paths
from meridian.lib.core.types import SpawnId
from meridian.lib.harness.connections.base import HarnessEvent
from meridian.lib.hcp.errors import HcpError, HcpErrorCategory
from meridian.lib.hcp.types import ChatState
from meridian.lib.state import session_store, spawn_store
from meridian.lib.state.history import HarnessHistoryWriter
from meridian.lib.state.paths import RuntimePaths, resolve_runtime_paths
from meridian.lib.streaming.drain_policy import TURN_BOUNDARY_EVENT_TYPE


class FakeHcpSessionManager:
    def __init__(self, runtime_root: Path) -> None:
        self.runtime_root = runtime_root
        self.states: dict[str, ChatState] = {}
        self.active_spawns: dict[str, SpawnId] = {}
        self.prompts: list[tuple[str, str]] = []
        self.concurrent_prompt = False

    async def create_chat(
        self,
        prompt: str,
        model: str | None = None,
        harness: str = "claude",
        *,
        config: Any,
        spec: Any,
        agent: str = "",
        agent_path: str = "",
        skills: tuple[str, ...] = (),
        skill_paths: tuple[str, ...] = (),
        params: tuple[str, ...] = (),
        harness_session_id: str = "",
        execution_cwd: str | None = None,
        metadata: Any = None,
    ) -> tuple[str, SpawnId]:
        _ = (spec, agent_path, skill_paths, params, metadata)
        c_id = session_store.start_session(
            self.runtime_root,
            harness=harness,
            harness_session_id=harness_session_id,
            model=model or "unknown",
            agent=agent,
            skills=skills,
            execution_cwd=execution_cwd,
            kind="primary",
        )
        p_id = spawn_store.start_spawn(
            self.runtime_root,
            chat_id=c_id,
            model=model or "unknown",
            agent=agent,
            skills=skills,
            harness=harness,
            kind="hcp",
            prompt=prompt,
            spawn_id=config.spawn_id,
            execution_cwd=execution_cwd,
            launch_mode="app",
        )
        self.states[c_id] = ChatState.ACTIVE
        self.active_spawns[c_id] = p_id
        return c_id, p_id

    def get_chat_state(self, c_id: str) -> ChatState | None:
        return self.states.get(c_id)

    def get_active_p_id(self, c_id: str) -> SpawnId | None:
        return self.active_spawns.get(c_id)

    async def prompt(self, c_id: str, text: str) -> None:
        if self.concurrent_prompt:
            raise HcpError(HcpErrorCategory.CONCURRENT_PROMPT, "chat already has active prompt")
        self.prompts.append((c_id, text))

    async def cancel(self, c_id: str) -> None:
        self.states[c_id] = ChatState.IDLE

    async def close_chat(self, c_id: str) -> None:
        self.active_spawns.pop(c_id, None)
        self.states[c_id] = ChatState.CLOSED
        session_store.stop_session(self.runtime_root, c_id)


def _make_client(tmp_path: Path) -> tuple[TestClient, FakeHcpSessionManager, Path]:
    runtime_root = resolve_runtime_paths(tmp_path).root_dir
    manager = FakeHcpSessionManager(runtime_root)
    app = FastAPI()
    app.state.hcp_session_manager = manager
    register_hcp_routes(
        app,
        manager,
        runtime_root,
        HTTPException,
        project_paths=resolve_project_config_paths(project_root=tmp_path),
    )
    return TestClient(app), manager, runtime_root


def _create_chat(client: TestClient) -> dict[str, Any]:
    response = client.post(
        "/api/chats",
        json={
            "prompt": "start a chat",
            "model": "gpt-5.4",
            "harness": "codex",
            "agent": "coder",
            "skills": ["dev-principles"],
        },
    )
    assert response.status_code == 201
    return response.json()


def _event_types(events: list[dict[str, Any]]) -> list[str]:
    return [str(event["type"]) for event in events]


def _paginate_cursor_history(
    client: TestClient,
    path: str,
    *,
    followup_limit: int | None = None,
) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    cursor: str | None = None

    while True:
        params: dict[str, str] = {}
        if cursor is not None:
            params["cursor"] = cursor
            if followup_limit is not None:
                params["limit"] = str(followup_limit)
        response = client.get(path, params=params)
        assert response.status_code == 200
        body = response.json()
        pages.append(body)
        if not body["has_more"]:
            assert body["next_cursor"] is None
            break
        assert body["next_cursor"] is not None
        cursor = body["next_cursor"]

    return pages


def test_create_list_get_prompt_cancel_and_close_chat(tmp_path: Path) -> None:
    client, manager, _runtime_root = _make_client(tmp_path)

    created = _create_chat(client)

    assert created["chat_id"] == "c1"
    assert created["state"] == "active"
    assert created["harness"] == "codex"
    assert created["model"] == "gpt-5.4"
    assert created["active_p_id"] == "p1"
    assert created["title"] is None
    assert created["updated_at"] is None
    assert created["spawns"][0]["spawn_id"] == "p1"

    list_response = client.get("/api/chats")
    assert list_response.status_code == 200
    assert [chat["chat_id"] for chat in list_response.json()] == ["c1"]

    detail_response = client.get("/api/chats/c1")
    assert detail_response.status_code == 200
    assert detail_response.json()["active_p_id"] == "p1"

    prompt_response = client.post("/api/chats/c1/prompt", json={"text": "continue"})
    assert prompt_response.status_code == 200
    assert prompt_response.json()["active_p_id"] == "p1"
    assert manager.prompts == [("c1", "continue")]

    cancel_response = client.post("/api/chats/c1/cancel")
    assert cancel_response.status_code == 200
    assert client.get("/api/chats/c1").json()["state"] == "idle"

    close_response = client.post("/api/chats/c1/close")
    assert close_response.status_code == 200
    assert client.get("/api/chats/c1").status_code == 404


def test_chat_routes_return_404_for_missing_chat(tmp_path: Path) -> None:
    client, _manager, _runtime_root = _make_client(tmp_path)

    assert client.get("/api/chats/c999").status_code == 404
    assert client.post("/api/chats/c999/prompt", json={"text": "hello"}).status_code == 404
    assert client.post("/api/chats/c999/cancel").status_code == 404
    assert client.post("/api/chats/c999/close").status_code == 404


def test_prompt_maps_concurrent_prompt_to_409(tmp_path: Path) -> None:
    client, manager, _runtime_root = _make_client(tmp_path)
    _create_chat(client)
    manager.concurrent_prompt = True

    response = client.post("/api/chats/c1/prompt", json={"text": "blocked"})

    assert response.status_code == 409
    assert response.json()["detail"] == "chat already has active prompt"


def test_chat_history_paginates_and_replays_agui_events(tmp_path: Path) -> None:
    client, _manager, runtime_root = _make_client(tmp_path)
    _create_chat(client)
    history_path = RuntimePaths.from_root_dir(runtime_root).spawn_history_path("p1")
    writer = HarnessHistoryWriter(history_path)
    writer.write(
        HarnessEvent(
            event_type="item/agentMessage",
            harness_id="codex",
            payload={"text": "skip"},
        )
    )
    writer.write(
        HarnessEvent(
            event_type="item/agentMessage",
            harness_id="codex",
            payload={"text": "keep"},
        )
    )

    response = client.get("/api/chats/c1/history", params={"start_seq": 1, "limit": 2})

    assert response.status_code == 200
    body = response.json()
    event_types = [event["type"] for event in body["events"]]
    assert event_types == [
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
    ]
    assert body["events"][0]["seq"] == 1
    assert body["has_more"] is True


def test_spawn_history_cursor_paginates_without_gaps_or_duplicates(tmp_path: Path) -> None:
    client, _manager, runtime_root = _make_client(tmp_path)
    _create_chat(client)
    history_path = RuntimePaths.from_root_dir(runtime_root).spawn_history_path("p1")
    writer = HarnessHistoryWriter(history_path)
    for turn in range(20):
        writer.write(
            HarnessEvent(
                event_type="item/agentMessage",
                harness_id="codex",
                payload={"text": f"turn {turn}"},
            )
        )
        writer.write(
            HarnessEvent(
                event_type="item/completed",
                harness_id="codex",
                payload={"item": {"type": "agentMessage"}},
            )
        )
        writer.write(
            HarnessEvent(
                event_type=TURN_BOUNDARY_EVENT_TYPE,
                harness_id="codex",
                payload={},
            )
        )
    writer.write(
        HarnessEvent(
            event_type="item/agentMessage",
            harness_id="codex",
            payload={"text": "turn 20"},
        )
    )
    writer.write(
        HarnessEvent(
            event_type="item/completed",
            harness_id="codex",
            payload={"item": {"type": "agentMessage"}},
        )
    )

    pages = _paginate_cursor_history(
        client,
        "/api/spawns/p1/history",
        followup_limit=4,
    )
    legacy_response = client.get(
        "/api/spawns/p1/history",
        params={"start_seq": 0, "limit": 1000},
    )
    assert legacy_response.status_code == 200

    paginated_events = [event for page in pages for event in page["events"]]
    assert _event_types(paginated_events) == _event_types(legacy_response.json())
    assert len(pages[0]["events"]) == 100
    assert pages[0]["events"][-1]["type"] == "RUN_FINISHED"
    assert pages[1]["events"][0]["type"] == "RUN_STARTED"


def test_chat_spawns_and_spawn_history(tmp_path: Path) -> None:
    client, _manager, runtime_root = _make_client(tmp_path)
    _create_chat(client)
    history_path = RuntimePaths.from_root_dir(runtime_root).spawn_history_path("p1")
    writer = HarnessHistoryWriter(history_path)
    writer.write(
        HarnessEvent(
            event_type="item/agentMessage",
            harness_id="codex",
            payload={"text": "spawn event"},
        )
    )

    spawns_response = client.get("/api/chats/c1/spawns")
    history_response = client.get("/api/spawns/p1/history")

    assert spawns_response.status_code == 200
    assert spawns_response.json()[0]["spawn_id"] == "p1"
    assert history_response.status_code == 200
    history_body = history_response.json()
    assert next(event["type"] for event in history_body["events"]) == "RUN_STARTED"
    assert history_body["next_cursor"] is None
    assert history_body["has_more"] is False


def test_spawn_history_paginates_in_agui_event_space(tmp_path: Path) -> None:
    client, _manager, runtime_root = _make_client(tmp_path)
    _create_chat(client)
    history_path = RuntimePaths.from_root_dir(runtime_root).spawn_history_path("p1")
    writer = HarnessHistoryWriter(history_path)
    writer.write(
        HarnessEvent(
            event_type="item/agentMessage",
            harness_id="codex",
            payload={"text": "skip"},
        )
    )
    writer.write(
        HarnessEvent(
            event_type="item/agentMessage",
            harness_id="codex",
            payload={"text": "keep"},
        )
    )

    response = client.get("/api/spawns/p1/history", params={"start_seq": 1, "limit": 2})

    assert response.status_code == 200
    assert [event["type"] for event in response.json()] == [
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
    ]


def test_spawn_history_uses_cursor_pagination_by_default(tmp_path: Path) -> None:
    client, _manager, runtime_root = _make_client(tmp_path)
    _create_chat(client)
    history_path = RuntimePaths.from_root_dir(runtime_root).spawn_history_path("p1")
    writer = HarnessHistoryWriter(history_path)
    for index in range(120):
        writer.write(
            HarnessEvent(
                event_type="item/agentMessage",
                harness_id="codex",
                payload={"text": f"message {index}"},
            )
        )

    first = client.get("/api/spawns/p1/history")

    assert first.status_code == 200
    first_body = first.json()
    assert first_body["events"][0]["type"] == "RUN_STARTED"
    assert len(first_body["events"]) == 100
    assert first_body["has_more"] is True
    assert first_body["next_cursor"] is not None

    second = client.get(
        "/api/spawns/p1/history",
        params={"cursor": first_body["next_cursor"], "limit": 10},
    )

    assert second.status_code == 200
    second_body = second.json()
    assert second_body["events"]
    assert second_body["events"][0]["seq"] == 0


def test_chat_history_cursor_paginates_across_spawns(tmp_path: Path) -> None:
    client, _manager, runtime_root = _make_client(tmp_path)
    _create_chat(client)
    runtime_paths = RuntimePaths.from_root_dir(runtime_root)
    writer_1 = HarnessHistoryWriter(runtime_paths.spawn_history_path("p1"))
    for turn in range(15):
        writer_1.write(
            HarnessEvent(
                event_type="item/agentMessage",
                harness_id="codex",
                payload={"text": f"first spawn {turn}"},
            )
        )
        writer_1.write(
            HarnessEvent(
                event_type="item/completed",
                harness_id="codex",
                payload={"item": {"type": "agentMessage"}},
            )
        )
        writer_1.write(
            HarnessEvent(
                event_type=TURN_BOUNDARY_EVENT_TYPE,
                harness_id="codex",
                payload={},
            )
        )
    spawn_store.start_spawn(
        runtime_root,
        chat_id="c1",
        model="gpt-5.4",
        agent="coder",
        skills=(),
        harness="codex",
        kind="hcp",
        prompt="second",
        spawn_id=SpawnId("p2"),
        execution_cwd=str(tmp_path),
        launch_mode="app",
    )
    writer_2 = HarnessHistoryWriter(runtime_paths.spawn_history_path("p2"))
    for turn in range(12):
        writer_2.write(
            HarnessEvent(
                event_type="item/agentMessage",
                harness_id="codex",
                payload={"text": f"second spawn {turn}"},
            )
        )
        writer_2.write(
            HarnessEvent(
                event_type="item/completed",
                harness_id="codex",
                payload={"item": {"type": "agentMessage"}},
            )
        )
        if turn < 11:
            writer_2.write(
                HarnessEvent(
                    event_type=TURN_BOUNDARY_EVENT_TYPE,
                    harness_id="codex",
                    payload={},
                )
            )

    pages = _paginate_cursor_history(
        client,
        "/api/chats/c1/history",
        followup_limit=4,
    )
    legacy_response = client.get(
        "/api/chats/c1/history",
        params={"start_seq": 0, "limit": 1000},
    )
    assert legacy_response.status_code == 200

    paginated_events = [event for page in pages for event in page["events"]]
    assert _event_types(paginated_events) == _event_types(legacy_response.json()["events"])
    assert len(pages[0]["events"]) == 100
    assert pages[0]["events"][-1]["type"] == "RUN_FINISHED"
    assert pages[1]["events"][0]["type"] == "RUN_STARTED"


def test_chat_history_cursor_keeps_turn_boundaries_consistent_across_pages(
    tmp_path: Path,
) -> None:
    client, _manager, runtime_root = _make_client(tmp_path)
    _create_chat(client)
    history_path = RuntimePaths.from_root_dir(runtime_root).spawn_history_path("p1")
    writer = HarnessHistoryWriter(history_path)
    for turn in range(20):
        writer.write(
            HarnessEvent(
                event_type="item/agentMessage",
                harness_id="codex",
                payload={"text": f"turn {turn}"},
            )
        )
        writer.write(
            HarnessEvent(
                event_type="item/completed",
                harness_id="codex",
                payload={"item": {"type": "agentMessage"}},
            )
        )
        writer.write(
            HarnessEvent(
                event_type=TURN_BOUNDARY_EVENT_TYPE,
                harness_id="codex",
                payload={},
            )
        )
    writer.write(
        HarnessEvent(
            event_type="item/agentMessage",
            harness_id="codex",
            payload={"text": "turn 20"},
        )
    )
    writer.write(
        HarnessEvent(
            event_type="item/completed",
            harness_id="codex",
            payload={"item": {"type": "agentMessage"}},
        )
    )

    pages = _paginate_cursor_history(
        client,
        "/api/chats/c1/history",
        followup_limit=4,
    )
    legacy_response = client.get(
        "/api/chats/c1/history",
        params={"start_seq": 0, "limit": 1000},
    )
    assert legacy_response.status_code == 200

    assert len(pages[0]["events"]) == 100
    assert pages[0]["events"][-1]["type"] == "RUN_FINISHED"
    assert pages[1]["events"][0]["type"] == "RUN_STARTED"
    paginated_events = [event for page in pages for event in page["events"]]
    assert _event_types(paginated_events) == _event_types(legacy_response.json()["events"])


def test_chat_history_cursor_beyond_spawn_list_returns_empty_page(tmp_path: Path) -> None:
    client, _manager, _runtime_root = _make_client(tmp_path)
    _create_chat(client)
    cursor = encode_pagination_cursor(
        PaginationCursor(raw_seq=0, agui_skip=0, checkpoint=0, spawn_idx=1)
    )

    response = client.get("/api/chats/c1/history", params={"cursor": cursor})

    assert response.status_code == 200
    assert response.json() == {
        "events": [],
        "next_cursor": None,
        "has_more": False,
    }


def test_history_routes_reject_invalid_cursor(tmp_path: Path) -> None:
    client, _manager, _runtime_root = _make_client(tmp_path)
    _create_chat(client)

    chat_response = client.get("/api/chats/c1/history", params={"cursor": "not-json"})
    spawn_response = client.get("/api/spawns/p1/history", params={"cursor": "not-json"})

    assert chat_response.status_code == 400
    assert spawn_response.status_code == 400
