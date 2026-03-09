"""Shared helpers for observing the latest harness session ID."""

from pathlib import Path

from meridian.lib.core.types import SpawnId
from meridian.lib.harness.adapter import ArtifactStore, HarnessAdapter


def _normalize_session_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def extract_latest_session_id(
    *,
    adapter: HarnessAdapter,
    current_session_id: str | None = None,
    artifacts: ArtifactStore | None = None,
    spawn_id: SpawnId | None = None,
    repo_root: Path | None = None,
    started_at_epoch: float | None = None,
    started_at_local_iso: str | None = None,
) -> str | None:
    """Return the best available latest session ID for a harness run.

    Priority order:
    1. Session ID emitted by this exact run's artifacts/output
    2. Adapter-native latest-session detection from harness state
    3. Previously known session ID
    """

    if artifacts is not None and spawn_id is not None:
        extracted = _normalize_session_id(adapter.extract_session_id(artifacts, spawn_id))
        if extracted is not None:
            return extracted

    if repo_root is not None and started_at_epoch is not None:
        detected = _normalize_session_id(
            adapter.detect_primary_session_id(
                repo_root=repo_root,
                started_at_epoch=started_at_epoch,
                started_at_local_iso=started_at_local_iso,
            )
        )
        if detected is not None:
            return detected

    return _normalize_session_id(current_session_id)


__all__ = ["extract_latest_session_id"]
