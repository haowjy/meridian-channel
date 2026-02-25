"""Harness adapter abstractions and built-in implementations."""

from meridian.lib.harness.adapter import (
    ArtifactStore,
    HarnessAdapter,
    HarnessCapabilities,
    PermissionResolver,
    RunParams,
    RunResult,
    StreamEvent,
)
from meridian.lib.harness.claude import ClaudeAdapter
from meridian.lib.harness.codex import CodexAdapter
from meridian.lib.harness.direct import DirectAdapter
from meridian.lib.harness.opencode import OpenCodeAdapter
from meridian.lib.harness.registry import HarnessRegistry, get_default_harness_registry

__all__ = [
    "ArtifactStore",
    "ClaudeAdapter",
    "CodexAdapter",
    "DirectAdapter",
    "HarnessAdapter",
    "HarnessCapabilities",
    "HarnessRegistry",
    "OpenCodeAdapter",
    "PermissionResolver",
    "RunParams",
    "RunResult",
    "StreamEvent",
    "get_default_harness_registry",
]
