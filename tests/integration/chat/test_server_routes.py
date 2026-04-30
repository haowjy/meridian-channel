from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from meridian.lib.chat.event_log import ChatEventLog
from meridian.lib.chat.protocol import ChatEvent, utc_now_iso
from meridian.lib.chat.server import app, configure
from meridian.lib.core.types import SpawnId
from meridian.lib.state.paths import RuntimePaths


class Handle:
    spawn_id = SpawnId("p-test")

    def health(self) -> bool:
        return True

    async def send_message(self, text: str) -> None:
        self.text = text

    async def send_cancel(self) -> None:
        pass

    async def stop(self) -> None:
        pass


class Acquisition:
    async def acquire(
        self,
        chat_id: str,
        initial_prompt: str,
        *,
        execution_generation: int = 0,
    ) -> Handle:
        _ = (chat_id, initial_prompt, execution_generation)
        return Handle()


def test_rest_routes_are_command_wrappers(tmp_path: Path) -> None:
    configure(runtime_root=tmp_path, backend_acquisition=Acquisition())
    with TestClient(app) as client:
        created = client.post("/chat", json={}).json()
        chat_id = created["chat_id"]
        assert created["state"] == "idle"

        assert client.get(f"/chat/{chat_id}/state").json()["state"] == "idle"
        assert client.post(f"/chat/{chat_id}/msg", json={"text": "hi"}).json() == {
            "status": "accepted",
            "error": None,
        }
        assert client.post(f"/chat/{chat_id}/cancel").json()["status"] == "accepted"
        assert client.post(f"/chat/{chat_id}/close").json()["status"] == "accepted"
        rejected = client.post(f"/chat/{chat_id}/msg", json={"text": "after"}).json()
        assert rejected["error"] == "chat_closed"
        assert client.get(f"/chat/{chat_id}/state").json()["state"] == "closed"


def test_list_chats_and_events_routes_expose_persisted_state(tmp_path: Path) -> None:
    configure(runtime_root=tmp_path, backend_acquisition=Acquisition())
    with TestClient(app) as client:
        chat_id = client.post("/chat", json={}).json()["chat_id"]

        listed = client.get("/chat").json()
        assert listed["chats"] == [
            {"chat_id": chat_id, "state": "idle", "created_at": listed["chats"][0]["created_at"]}
        ]
        assert listed["chats"][0]["created_at"]

        events = client.get(f"/chat/{chat_id}/events").json()
        assert events["chat_id"] == chat_id
        assert [event["type"] for event in events["events"]] == ["chat.started"]

        prompted = client.post(f"/chat/{chat_id}/msg", json={"text": "hi"}).json()
        assert prompted["status"] == "accepted"
        limited = client.get(f"/chat/{chat_id}/events?last=1").json()
        assert len(limited["events"]) == 1
        assert limited["events"][0]["type"]


def test_events_route_rejects_unknown_chat(tmp_path: Path) -> None:
    configure(runtime_root=tmp_path, backend_acquisition=Acquisition())
    with TestClient(app) as client:
        response = client.get("/chat/c-missing/events")
        assert response.status_code == 404


def test_restart_recovery_marks_unclosed_active_chat_idle_with_error(tmp_path: Path) -> None:
    configure(runtime_root=tmp_path, backend_acquisition=Acquisition())
    with TestClient(app) as client:
        chat_id = client.post("/chat", json={}).json()["chat_id"]
        prompted = client.post(f"/chat/{chat_id}/msg", json={"text": "hi"}).json()
        assert prompted["status"] == "accepted"

    log = ChatEventLog(RuntimePaths.from_root_dir(tmp_path).chat_history_path(chat_id))
    log.append(
        ChatEvent(
            type="turn.started",
            seq=0,
            chat_id=chat_id,
            execution_id="p-test",
            timestamp=utc_now_iso(),
        )
    )

    configure(runtime_root=tmp_path, backend_acquisition=Acquisition())
    with TestClient(app) as client:
        assert client.get(f"/chat/{chat_id}/state").json()["state"] == "idle"
        with client.websocket_connect(f"/ws/chat/{chat_id}") as ws:
            events = [ws.receive_json(), ws.receive_json(), ws.receive_json()]
        assert [event["type"] for event in events] == [
            "chat.started",
            "turn.started",
            "runtime.error",
        ]
