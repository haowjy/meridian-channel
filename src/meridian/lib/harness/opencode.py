"""OpenCode CLI harness adapter."""

from __future__ import annotations

from meridian.lib.harness._common import (
    extract_session_id_from_artifacts,
    extract_usage_from_artifacts,
    parse_json_stream_event,
)
from meridian.lib.harness.adapter import (
    ArtifactStore,
    HarnessCapabilities,
    PermissionResolver,
    RunParams,
    StreamEvent,
)
from meridian.lib.types import HarnessId, RunId


def _strip_opencode_prefix(model: str) -> str:
    return model[len("opencode-") :] if model.startswith("opencode-") else model


class OpenCodeAdapter:
    """HarnessAdapter implementation for `opencode`."""

    @property
    def id(self) -> HarnessId:
        return HarnessId("opencode")

    @property
    def capabilities(self) -> HarnessCapabilities:
        return HarnessCapabilities(
            supports_stream_events=True,
            supports_session_resume=True,
            supports_native_skills=True,
            supports_programmatic_tools=False,
        )

    def build_command(self, run: RunParams, perms: PermissionResolver) -> list[str]:
        model = _strip_opencode_prefix(str(run.model))
        command = ["opencode", "run", "--model", model, run.prompt]
        if run.agent:
            command.extend(["--agent", run.agent])
        if run.skills:
            command.extend(["--skills", ",".join(run.skills)])
        command.extend(perms.resolve_flags(self.id))
        command.extend(run.extra_args)
        return command

    def parse_stream_event(self, line: str) -> StreamEvent | None:
        return parse_json_stream_event(line)

    def extract_usage(self, artifacts: ArtifactStore, run_id: RunId):
        return extract_usage_from_artifacts(artifacts, run_id)

    def extract_session_id(self, artifacts: ArtifactStore, run_id: RunId) -> str | None:
        return extract_session_id_from_artifacts(artifacts, run_id)

