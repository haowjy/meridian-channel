"""Compatibility shim for artifact read helpers."""

from __future__ import annotations

from meridian.lib.launch.artifact_io import read_artifact_text as _read_artifact_text
from meridian.lib.state.artifact_store import ArtifactStore
from meridian.lib.types import SpawnId


def read_artifact_text(artifacts: ArtifactStore, spawn_id: SpawnId, name: str) -> str:
    return _read_artifact_text(artifacts, spawn_id, name)
