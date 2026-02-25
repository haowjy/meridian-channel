"""Claude CLI harness adapter."""

from __future__ import annotations

from typing import ClassVar

from meridian.lib.harness._common import (
    extract_session_id_from_artifacts,
    extract_usage_from_artifacts,
    parse_json_stream_event,
)
from meridian.lib.harness._strategies import (
    FlagEffect,
    FlagStrategy,
    PromptMode,
    StrategyMap,
    build_harness_command,
)
from meridian.lib.harness.adapter import (
    ArtifactStore,
    HarnessCapabilities,
    PermissionResolver,
    RunParams,
    StreamEvent,
)
from meridian.lib.types import HarnessId, RunId


class ClaudeAdapter:
    """HarnessAdapter implementation for `claude`."""

    STRATEGIES: ClassVar[StrategyMap] = {
        "model": FlagStrategy(effect=FlagEffect.CLI_FLAG, cli_flag="--model"),
        "agent": FlagStrategy(effect=FlagEffect.CLI_FLAG, cli_flag="--agent"),
        "skills": FlagStrategy(effect=FlagEffect.DROP),
    }
    PROMPT_MODE: ClassVar[PromptMode] = PromptMode.FLAG
    BASE_COMMAND: ClassVar[tuple[str, ...]] = ("claude", "-p")

    @property
    def id(self) -> HarnessId:
        return HarnessId("claude")

    @property
    def capabilities(self) -> HarnessCapabilities:
        return HarnessCapabilities(
            supports_stream_events=True,
            supports_session_resume=True,
            supports_native_skills=True,
            supports_programmatic_tools=False,
        )

    def build_command(self, run: RunParams, perms: PermissionResolver) -> list[str]:
        return build_harness_command(
            base_command=self.BASE_COMMAND,
            prompt_mode=self.PROMPT_MODE,
            run=run,
            strategies=self.STRATEGIES,
            perms=perms,
            harness_id=self.id,
        )

    def parse_stream_event(self, line: str) -> StreamEvent | None:
        return parse_json_stream_event(line)

    def extract_usage(self, artifacts: ArtifactStore, run_id: RunId):
        return extract_usage_from_artifacts(artifacts, run_id)

    def extract_session_id(self, artifacts: ArtifactStore, run_id: RunId) -> str | None:
        return extract_session_id_from_artifacts(artifacts, run_id)
