"""KG analysis API route handlers.

Exposes knowledge-graph analysis through project-root-relative API
endpoints:

- GET /api/kg/graph — full graph analysis as JSON
- GET /api/kg/check — targeted analysis for a single file or directory
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

from meridian.lib.app.http_types import HTTPExceptionCallable
from meridian.lib.app.path_security import PathSecurityError, validate_project_path


class _FastAPIApp(Protocol):
    """Minimal FastAPI app surface consumed by this module."""

    def get(self, path: str, **kwargs: object) -> Callable[[Callable[..., object]], object]: ...


def register_kg_routes(
    app: object,
    *,
    project_root: Path,
    http_exception: HTTPExceptionCallable,
) -> None:
    """Register ``/api/kg/*`` routes on the FastAPI app.

    All user-supplied paths are validated through ``validate_project_path`` to
    ensure they stay within ``project_root``. Paths that escape the project
    root (absolute paths, UNC, Windows drives, ``..`` traversal) are rejected
    with 403 Forbidden.
    """

    from importlib import import_module

    try:
        fastapi_module = import_module("fastapi")
        Query = fastapi_module.Query
    except ModuleNotFoundError as exc:
        msg = "FastAPI is required for KG routes."
        raise RuntimeError(msg) from exc

    typed_app = cast("_FastAPIApp", app)

    async def kg_graph(
        root: str = Query(default=".", description="Root directory to analyze"),
        no_backlinks: bool = Query(
            default=False,
            description="Skip missing-backlink analysis",
        ),
        no_clusters: bool = Query(default=False, description="Skip cluster analysis"),
    ) -> dict[str, object]:
        """Analyze document relationships and return the full graph as JSON."""

        from meridian.lib.kg.graph import build_analysis
        from meridian.lib.kg.serializer import serialize_analysis

        try:
            root_path = validate_project_path(project_root, root)
        except PathSecurityError as exc:
            raise http_exception(status_code=403, detail=str(exc)) from exc

        if not root_path.exists():
            raise http_exception(status_code=404, detail=f"root not found: {root}")
        if not root_path.is_dir():
            raise http_exception(status_code=400, detail=f"root is not a directory: {root}")

        result = build_analysis(
            root=root_path,
            include_backlinks=not no_backlinks,
            include_clusters=not no_clusters,
        )
        return serialize_analysis(result, root_path)

    async def kg_check(
        path: str = Query(..., description="File or directory to analyze"),
    ) -> dict[str, object]:
        """Check for broken links in a file or directory."""

        from meridian.lib.kg.graph import build_analysis
        from meridian.lib.kg.serializer import serialize_check

        try:
            resolved = validate_project_path(project_root, path)
        except PathSecurityError as exc:
            raise http_exception(status_code=403, detail=str(exc)) from exc

        if not resolved.exists():
            raise http_exception(status_code=404, detail=f"path not found: {path}")

        root = resolved if resolved.is_dir() else resolved.parent
        result = build_analysis(
            root=root,
            include_backlinks=False,
            include_clusters=False,
        )
        return serialize_check(result, resolved)

    typed_app.get("/api/kg/graph")(kg_graph)
    typed_app.get("/api/kg/check")(kg_check)


__all__ = ["register_kg_routes"]
