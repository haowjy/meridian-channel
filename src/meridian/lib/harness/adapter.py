"""Harness adapter protocol and shared data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from meridian.lib.domain import TokenUsage
from meridian.lib.safety.permissions import PermissionConfig
from meridian.lib.types import ArtifactKey, HarnessId, ModelId, RunId


def _empty_metadata() -> dict[str, object]:
    return {}


def _empty_env_overrides() -> dict[str, str]:
    return {}


@dataclass(frozen=True, slots=True)
class HarnessCapabilities:
    """Feature flags for one harness implementation."""

    supports_stream_events: bool = True
    supports_session_resume: bool = False
    supports_session_fork: bool = False
    supports_native_skills: bool = False
    supports_programmatic_tools: bool = False


@dataclass(frozen=True, slots=True)
class RunParams:
    """Inputs required to launch one harness run."""

    prompt: str
    model: ModelId
    skills: tuple[str, ...] = ()
    agent: str | None = None
    extra_args: tuple[str, ...] = ()
    repo_root: str | None = None
    mcp_tools: tuple[str, ...] = ()
    continue_session_id: str | None = None
    continue_fork: bool = False


@dataclass(frozen=True, slots=True)
class McpConfig:
    """Harness-specific MCP wiring details for one run."""

    command_args: tuple[str, ...] = ()
    env_overrides: dict[str, str] = field(default_factory=_empty_env_overrides)
    claude_allowed_tools: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StreamEvent:
    """Structured stream event parsed from harness output."""

    event_type: str
    category: str
    raw_line: str
    text: str | None = None
    metadata: dict[str, object] = field(default_factory=_empty_metadata)


@dataclass(frozen=True, slots=True)
class RunResult:
    """Result payload for one completed execution."""

    status: str
    output: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    session_id: str | None = None
    raw_response: dict[str, object] | None = None


class PermissionResolver(Protocol):
    """Permission resolver provided by execution layer."""

    def resolve_flags(self, harness_id: HarnessId) -> list[str]: ...


class ArtifactStore(Protocol):
    """Artifact access used for usage/session extraction."""

    def get(self, key: ArtifactKey) -> bytes: ...

    def exists(self, key: ArtifactKey) -> bool: ...


class HarnessAdapter(Protocol):
    """Protocol for harness-specific launch/parsing/extraction behavior."""

    @property
    def id(self) -> HarnessId: ...

    @property
    def capabilities(self) -> HarnessCapabilities: ...

    def build_command(self, run: RunParams, perms: PermissionResolver) -> list[str]: ...

    def mcp_config(self, run: RunParams) -> McpConfig | None: ...

    def env_overrides(self, config: PermissionConfig) -> dict[str, str]: ...

    def parse_stream_event(self, line: str) -> StreamEvent | None: ...

    def extract_usage(self, artifacts: ArtifactStore, run_id: RunId) -> TokenUsage: ...

    def extract_session_id(self, artifacts: ArtifactStore, run_id: RunId) -> str | None: ...

    def extract_tasks(self, event: StreamEvent) -> list[dict[str, str]] | None:
        """Extract structured task updates from one stream event."""

        _ = event
        return None

    def extract_findings(self, event: StreamEvent) -> list[dict[str, str]] | None:
        """Extract structured findings from one stream event."""

        _ = event
        return None

    def extract_summary(self, output: str) -> str | None:
        """Extract a concise run summary from final output text."""

        _ = output
        return None


def resolve_mcp_config(adapter: HarnessAdapter, run: RunParams) -> McpConfig | None:
    """Resolve adapter MCP config if the adapter implements the optional hook."""

    resolver = getattr(adapter, "mcp_config", None)
    if resolver is None:
        return None
    return resolver(run)
