"""AG-UI mapper selection for each harness."""

from __future__ import annotations

from meridian.lib.app.agui_mapping.base import AGUIMapper
from meridian.lib.app.agui_mapping.claude import ClaudeAGUIMapper
from meridian.lib.app.agui_mapping.codex import CodexAGUIMapper
from meridian.lib.app.agui_mapping.opencode import OpenCodeAGUIMapper
from meridian.lib.core.types import HarnessId


def get_agui_mapper(harness_id: HarnessId) -> AGUIMapper:
    """Return the AG-UI mapper for one harness."""

    mappers = {
        HarnessId.CLAUDE: ClaudeAGUIMapper,
        HarnessId.CODEX: CodexAGUIMapper,
        HarnessId.OPENCODE: OpenCodeAGUIMapper,
    }
    cls = mappers.get(harness_id)
    if cls is None:
        raise ValueError(f"No AG-UI mapper for {harness_id}")
    return cls()


__all__ = ["AGUIMapper", "get_agui_mapper"]
