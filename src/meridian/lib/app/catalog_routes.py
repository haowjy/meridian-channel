"""Catalog route handlers: /api/models and /api/agents.

Both endpoints are read-only and stateless — they delegate discovery to the
existing catalog layer rather than maintaining any in-process cache.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

from meridian.lib.app.api_models import AgentSummary
from meridian.lib.app.http_types import HTTPExceptionCallable
from meridian.lib.catalog.agent import scan_agent_profiles
from meridian.lib.ops.catalog import ModelsListInput, models_list_sync


class _FastAPIApp(Protocol):
    """Minimal FastAPI app surface consumed by this module."""

    def get(self, path: str, **kwargs: object) -> Callable[[Callable[..., object]], object]: ...


def register_catalog_routes(
    app: object,
    *,
    project_root: Path,
    http_exception: HTTPExceptionCallable,
) -> None:
    """Register /api/models and /api/agents routes on *app*."""

    typed_app = cast("_FastAPIApp", app)
    _ = http_exception  # reserved for future error handling

    async def list_models() -> dict[str, object]:
        """Return all discoverable models in wire format.

        Delegates to ``models_list_sync`` which applies default visibility
        filtering (pinned + recent models visible, old superseded models hidden).
        """
        output = models_list_sync(ModelsListInput())
        return {"models": [m.to_wire() for m in output.models]}

    async def list_agents() -> dict[str, object]:
        """Return agent profile summaries discovered from ``.agents/agents/*.md``.

        Returns an empty list when the agents directory does not exist.
        """
        profiles = scan_agent_profiles(project_root=project_root)
        agents: list[AgentSummary] = [
            AgentSummary(
                name=profile.name,
                description=profile.description,
                model=profile.model,
                harness=profile.harness,
                skills=list(profile.skills),
                path=profile.path.name,
            )
            for profile in profiles
        ]
        return {"agents": [a.model_dump(exclude_none=False) for a in agents]}

    typed_app.get("/api/models")(list_models)
    typed_app.get("/api/agents")(list_agents)


__all__ = ["register_catalog_routes"]
