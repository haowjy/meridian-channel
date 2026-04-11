"""Spawn extractor wrapper backed by harness-owned extractors."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from meridian.lib.core.domain import TokenUsage
from meridian.lib.core.types import SpawnId
from meridian.lib.harness.adapter import ArtifactStore, SpawnExtractor
from meridian.lib.harness.bundle import HarnessBundle
from meridian.lib.harness.connections.base import HarnessConnection
from meridian.lib.launch.launch_types import ResolvedLaunchSpec


class StreamingExtractor(SpawnExtractor):
    """Compatibility wrapper delegating extraction to one harness bundle."""

    def __init__(
        self,
        *,
        connection: HarnessConnection[Any] | None,
        bundle: HarnessBundle[Any],
        spec: ResolvedLaunchSpec,
        launch_env: Mapping[str, str],
        child_cwd: Path,
        state_root: Path,
    ) -> None:
        if not isinstance(spec, bundle.spec_cls):
            raise TypeError(
                f"HarnessBundle invariant violated: extractor for {bundle.harness_id} "
                f"received {type(spec).__name__}, expected {bundle.spec_cls.__name__}"
            )

        self._connection = connection
        self._bundle = bundle
        self._spec = spec
        self._launch_env = launch_env
        self._child_cwd = child_cwd
        self._state_root = state_root

    def extract_session_id(self, artifacts: ArtifactStore, spawn_id: SpawnId) -> str | None:
        connection = self._connection
        if connection is not None:
            live_session_id = connection.session_id
            if live_session_id:
                return live_session_id

        extracted = self._bundle.extractor.extract_session_id(artifacts, spawn_id)
        if extracted:
            return extracted

        return self._bundle.extractor.detect_session_id_from_artifacts(
            spec=self._spec,
            launch_env=self._launch_env,
            child_cwd=self._child_cwd,
            state_root=self._state_root,
        )

    def extract_usage(self, artifacts: ArtifactStore, spawn_id: SpawnId) -> TokenUsage:
        return self._bundle.extractor.extract_usage(artifacts, spawn_id)

    def extract_report(self, artifacts: ArtifactStore, spawn_id: SpawnId) -> str | None:
        return self._bundle.extractor.extract_report(artifacts, spawn_id)


__all__ = ["StreamingExtractor"]
