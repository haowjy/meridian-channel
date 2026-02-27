"""Claude CLI harness adapter."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import ClassVar

from meridian.lib.harness._common import (
    categorize_stream_event,
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
    McpConfig,
    PermissionResolver,
    RunParams,
    StreamEvent,
)
from meridian.lib.safety.permissions import PermissionConfig
from meridian.lib.types import HarnessId, RunId


class ClaudeAdapter:
    """HarnessAdapter implementation for `claude`."""

    STRATEGIES: ClassVar[StrategyMap] = {
        "model": FlagStrategy(effect=FlagEffect.CLI_FLAG, cli_flag="--model"),
        "agent": FlagStrategy(effect=FlagEffect.DROP),
        "skills": FlagStrategy(effect=FlagEffect.DROP),
    }
    PROMPT_MODE: ClassVar[PromptMode] = PromptMode.FLAG
    BASE_COMMAND: ClassVar[tuple[str, ...]] = ("claude", "-p")
    EVENT_CATEGORY_MAP: ClassVar[dict[str, str]] = {
        "result": "lifecycle",
        "tool_use": "tool-use",
        "assistant": "assistant",
        "thinking": "thinking",
        "error": "error",
    }
    MCP_CONFIG_PREFIX: ClassVar[str] = "meridian-claude-mcp"

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
        mcp_config = self.mcp_config(run)
        return build_harness_command(
            base_command=self.BASE_COMMAND,
            prompt_mode=self.PROMPT_MODE,
            run=run,
            strategies=self.STRATEGIES,
            perms=perms,
            harness_id=self.id,
            mcp_config=mcp_config,
        )

    def _mcp_config_path(self, run: RunParams) -> Path:
        repo_root = (run.repo_root or "").strip() or "."
        fingerprint = hashlib.sha256(
            f"{repo_root}|{','.join(run.mcp_tools)}".encode("utf-8")
        ).hexdigest()[:16]
        return Path(tempfile.gettempdir()) / f"{self.MCP_CONFIG_PREFIX}-{fingerprint}.json"

    def _write_mcp_config(self, run: RunParams) -> Path:
        repo_root = (run.repo_root or "").strip() or "."
        payload = {
            "mcpServers": {
                "meridian": {
                    "command": "uv",
                    "args": ["run", "--directory", repo_root, "meridian", "serve"],
                }
            }
        }
        path = self._mcp_config_path(run)
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        return path

    def mcp_config(self, run: RunParams) -> McpConfig | None:
        if run.repo_root is None or not run.repo_root.strip():
            return None
        mcp_file = self._write_mcp_config(run)
        if run.mcp_tools:
            allowed_tools = tuple(f"mcp__meridian__{tool}" for tool in run.mcp_tools)
        else:
            allowed_tools = ("mcp__meridian__*",)

        # MCP sidecar crash behavior:
        # Claude surfaces MCP transport failures in-stream and the run usually exits
        # non-zero; Meridian treats this as a failed attempt and does not reconnect.
        return McpConfig(
            command_args=("--mcp-config", mcp_file.as_posix()),
            claude_allowed_tools=allowed_tools,
        )

    def env_overrides(self, config: PermissionConfig) -> dict[str, str]:
        _ = config
        return {}

    def parse_stream_event(self, line: str) -> StreamEvent | None:
        event = parse_json_stream_event(line)
        if event is None:
            return None
        return categorize_stream_event(event, exact_map=self.EVENT_CATEGORY_MAP)

    def extract_usage(self, artifacts: ArtifactStore, run_id: RunId):
        return extract_usage_from_artifacts(artifacts, run_id)

    def extract_session_id(self, artifacts: ArtifactStore, run_id: RunId) -> str | None:
        return extract_session_id_from_artifacts(artifacts, run_id)
