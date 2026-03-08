"""Compatibility shims for model catalog operations."""

from __future__ import annotations

from meridian.lib.config.aliases import load_merged_aliases, resolve_model
from meridian.lib.config.discovery import load_discovered_models, refresh_models_cache
from meridian.lib.config.routing import route_model
from meridian.lib.ops import catalog as _catalog
from meridian.lib.ops.catalog import (
    CatalogModel,
    ModelsListInput,
    ModelsListOutput,
    ModelsRefreshInput,
    ModelsRefreshOutput,
    ModelsShowInput,
)


def _sync_catalog_bindings() -> None:
    _catalog.load_merged_aliases = load_merged_aliases
    _catalog.load_discovered_models = load_discovered_models
    _catalog.refresh_models_cache = refresh_models_cache
    _catalog.resolve_model = resolve_model
    _catalog.route_model = route_model


def models_list_sync(payload: ModelsListInput) -> ModelsListOutput:
    _sync_catalog_bindings()
    return _catalog.models_list_sync(payload)


def models_show_sync(payload: ModelsShowInput) -> CatalogModel:
    _sync_catalog_bindings()
    return _catalog.models_show_sync(payload)


def models_refresh_sync(payload: ModelsRefreshInput) -> ModelsRefreshOutput:
    _sync_catalog_bindings()
    return _catalog.models_refresh_sync(payload)


async def models_list(payload: ModelsListInput) -> ModelsListOutput:
    _sync_catalog_bindings()
    return await _catalog.models_list(payload)


async def models_show(payload: ModelsShowInput) -> CatalogModel:
    _sync_catalog_bindings()
    return await _catalog.models_show(payload)


async def models_refresh(payload: ModelsRefreshInput) -> ModelsRefreshOutput:
    _sync_catalog_bindings()
    return await _catalog.models_refresh(payload)


__all__ = [
    "CatalogModel",
    "ModelsListInput",
    "ModelsListOutput",
    "ModelsRefreshInput",
    "ModelsRefreshOutput",
    "ModelsShowInput",
    "load_discovered_models",
    "load_merged_aliases",
    "models_list",
    "models_list_sync",
    "models_refresh",
    "models_refresh_sync",
    "models_show",
    "models_show_sync",
    "refresh_models_cache",
    "resolve_model",
    "route_model",
]
