"""FastAPI application factory for Meridian app endpoints."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib import import_module
from typing import Protocol, cast

from meridian.lib.streaming.spawn_manager import SpawnManager


class _AppState(Protocol):
    """App state payload carrying shared runtime singletons."""

    spawn_manager: SpawnManager


class _FastAPIApp(Protocol):
    """Minimal FastAPI app surface consumed by this module."""

    state: _AppState

    def add_middleware(self, middleware_class: type[object], **kwargs: object) -> None: ...


class _FastAPIFactory(Protocol):
    """Callable FastAPI constructor surface used by create_app()."""

    def __call__(self, *, title: str, lifespan: object) -> object: ...


class _FastAPIModule(Protocol):
    FastAPI: _FastAPIFactory


class _FastAPICorsModule(Protocol):
    CORSMiddleware: type[object]


def create_app(spawn_manager: SpawnManager) -> object:
    """Create the FastAPI application for Meridian app."""

    @asynccontextmanager
    async def lifespan(_: object) -> AsyncIterator[None]:
        # SpawnManager lifecycle is owned by caller for startup.
        yield
        await spawn_manager.shutdown()

    try:
        fastapi_module = import_module("fastapi")
        cors_module = import_module("fastapi.middleware.cors")
    except ModuleNotFoundError as exc:
        msg = (
            "FastAPI app dependencies are not installed. "
            "Run `uv sync --extra app --extra dev`."
        )
        raise RuntimeError(msg) from exc

    fastapi = cast("_FastAPIModule", fastapi_module)
    cors = cast("_FastAPICorsModule", cors_module)
    app_obj = fastapi.FastAPI(title="Meridian App", lifespan=lifespan)
    app = cast("_FastAPIApp", app_obj)

    app.add_middleware(
        cors.CORSMiddleware,
        allow_origins=[],
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.spawn_manager = spawn_manager

    from meridian.lib.app.ws_endpoint import register_ws_routes

    register_ws_routes(app_obj, spawn_manager)

    return app_obj


__all__ = ["create_app"]
