from pathlib import Path

from meridian.lib.core.types import HarnessId, SpawnId
from meridian.lib.harness.adapter import BaseHarnessAdapter, HarnessCapabilities
from meridian.lib.launch.session_ids import extract_latest_session_id
from meridian.lib.state.artifact_store import InMemoryStore, make_artifact_key


class _StubAdapter(BaseHarnessAdapter):
    def __init__(
        self,
        *,
        extracted_session_id: str | None = None,
        detected_session_id: str | None = None,
    ) -> None:
        self._extracted_session_id = extracted_session_id
        self._detected_session_id = detected_session_id

    @property
    def id(self) -> HarnessId:
        return HarnessId("stub")

    @property
    def capabilities(self) -> HarnessCapabilities:
        return HarnessCapabilities()

    def extract_session_id(self, artifacts, spawn_id: SpawnId) -> str | None:
        _ = artifacts, spawn_id
        return self._extracted_session_id

    def detect_primary_session_id(
        self,
        *,
        repo_root: Path,
        started_at_epoch: float,
        started_at_local_iso: str | None,
    ) -> str | None:
        _ = repo_root, started_at_epoch, started_at_local_iso
        return self._detected_session_id


def test_extract_latest_session_id_prefers_run_artifacts() -> None:
    artifacts = InMemoryStore()
    spawn_id = SpawnId("r-artifacts-win")
    artifacts.put(make_artifact_key(spawn_id, "output.jsonl"), b'{"sessionId":"artifact-session"}\n')

    adapter = _StubAdapter(
        extracted_session_id="artifact-session",
        detected_session_id="native-session",
    )

    assert (
        extract_latest_session_id(
            adapter=adapter,
            current_session_id="seed-session",
            artifacts=artifacts,
            spawn_id=spawn_id,
            repo_root=Path("/tmp/repo"),
            started_at_epoch=1.0,
            started_at_local_iso="2026-03-09T10:00:00",
        )
        == "artifact-session"
    )


def test_extract_latest_session_id_falls_back_to_native_detection_then_current() -> None:
    adapter = _StubAdapter(
        extracted_session_id=None,
        detected_session_id="native-session",
    )

    assert (
        extract_latest_session_id(
            adapter=adapter,
            current_session_id="seed-session",
            repo_root=Path("/tmp/repo"),
            started_at_epoch=1.0,
            started_at_local_iso="2026-03-09T10:00:00",
        )
        == "native-session"
    )

    adapter = _StubAdapter(
        extracted_session_id=None,
        detected_session_id=None,
    )
    assert (
        extract_latest_session_id(
            adapter=adapter,
            current_session_id="seed-session",
        )
        == "seed-session"
    )
