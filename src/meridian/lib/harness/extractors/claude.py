"""Claude harness extractor."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from meridian.lib.core.domain import TokenUsage
from meridian.lib.core.types import SpawnId
from meridian.lib.harness.adapter import ArtifactStore
from meridian.lib.harness.common import (
    extract_claude_report,
    extract_session_id_from_artifacts,
    extract_usage_from_artifacts,
)
from meridian.lib.harness.connections.base import HarnessEvent
from meridian.lib.harness.launch_spec import ClaudeLaunchSpec

from .base import HarnessExtractor


def _session_from_mapping(payload: Mapping[str, object]) -> str | None:
    for key in ("session_id", "sessionId", "sessionID"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for nested in payload.values():
        if isinstance(nested, dict):
            found = _session_from_mapping(cast("dict[str, object]", nested))
            if found:
                return found
    return None


def _project_slug(path: Path) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "-", str(path.resolve()))


def _detect_primary_session_id(
    *,
    child_cwd: Path,
    launch_env: Mapping[str, str],
) -> str | None:
    home = launch_env.get("HOME", "").strip()
    home_path = Path(home).expanduser() if home else Path.home()
    projects_root = home_path / ".claude" / "projects"
    project_dir = projects_root / _project_slug(child_cwd)
    if not project_dir.is_dir():
        return None

    candidates: list[tuple[float, Path]] = []
    for candidate in project_dir.glob("*.jsonl"):
        try:
            modified_at = candidate.stat().st_mtime
        except OSError:
            continue
        candidates.append((modified_at, candidate))

    for _, candidate in sorted(candidates, key=lambda item: item[0], reverse=True):
        try:
            first_line = candidate.read_text(encoding="utf-8", errors="ignore").splitlines()[0]
        except (OSError, IndexError):
            first_line = ""
        if not first_line.strip():
            continue
        try:
            payload_obj = json.loads(first_line)
        except json.JSONDecodeError:
            payload_obj = None
        if isinstance(payload_obj, dict):
            payload = cast("dict[str, object]", payload_obj)
            session_id = payload.get("sessionId")
            if isinstance(session_id, str) and session_id.strip():
                return session_id.strip()
        if candidate.stem.strip():
            return candidate.stem.strip()

    return None


class ClaudeHarnessExtractor(HarnessExtractor[ClaudeLaunchSpec]):
    """Extractor implementation for Claude artifacts and events."""

    def detect_session_id_from_event(self, event: HarnessEvent) -> str | None:
        return _session_from_mapping(event.payload)

    def detect_session_id_from_artifacts(
        self,
        *,
        spec: ClaudeLaunchSpec,
        launch_env: Mapping[str, str],
        child_cwd: Path,
        state_root: Path,
    ) -> str | None:
        _ = state_root
        if spec.continue_session_id and spec.continue_session_id.strip():
            return spec.continue_session_id.strip()
        return _detect_primary_session_id(child_cwd=child_cwd, launch_env=launch_env)

    def extract_usage(self, artifacts: ArtifactStore, spawn_id: SpawnId) -> TokenUsage:
        return extract_usage_from_artifacts(artifacts, spawn_id)

    def extract_session_id(self, artifacts: ArtifactStore, spawn_id: SpawnId) -> str | None:
        return extract_session_id_from_artifacts(artifacts, spawn_id)

    def extract_report(self, artifacts: ArtifactStore, spawn_id: SpawnId) -> str | None:
        return extract_claude_report(artifacts, spawn_id)


CLAUDE_EXTRACTOR = ClaudeHarnessExtractor()

__all__ = ["CLAUDE_EXTRACTOR", "ClaudeHarnessExtractor"]
