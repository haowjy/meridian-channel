"""Shared artifact read helpers for extraction modules."""

from __future__ import annotations

from meridian.lib.state.artifact_store import ArtifactStore
from meridian.lib.types import ArtifactKey, RunId


def _read_artifact_text(artifacts: ArtifactStore, run_id: RunId, name: str) -> str:
    key = ArtifactKey(f"{run_id}/{name}")
    if not artifacts.exists(key):
        return ""
    return artifacts.get(key).decode("utf-8", errors="ignore")
