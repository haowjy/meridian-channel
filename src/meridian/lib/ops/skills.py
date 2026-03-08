"""Compatibility shims for skill catalog operations."""

from __future__ import annotations

from meridian.lib.config.skill_registry import SkillRegistry
from meridian.lib.domain import SkillContent
from meridian.lib.ops import catalog as _catalog
from meridian.lib.ops.catalog import (
    SkillsListInput,
    SkillsLoadInput,
    SkillsQueryOutput,
    SkillsSearchInput,
)


def _sync_catalog_bindings() -> None:
    _catalog.SkillRegistry = SkillRegistry


def skills_list_sync(payload: SkillsListInput) -> SkillsQueryOutput:
    _sync_catalog_bindings()
    return _catalog.skills_list_sync(payload)


def skills_search_sync(payload: SkillsSearchInput) -> SkillsQueryOutput:
    _sync_catalog_bindings()
    return _catalog.skills_search_sync(payload)


def skills_load_sync(payload: SkillsLoadInput) -> SkillContent:
    _sync_catalog_bindings()
    return _catalog.skills_load_sync(payload)


async def skills_list(payload: SkillsListInput) -> SkillsQueryOutput:
    _sync_catalog_bindings()
    return await _catalog.skills_list(payload)


async def skills_search(payload: SkillsSearchInput) -> SkillsQueryOutput:
    _sync_catalog_bindings()
    return await _catalog.skills_search(payload)


async def skills_load(payload: SkillsLoadInput) -> SkillContent:
    _sync_catalog_bindings()
    return await _catalog.skills_load(payload)


__all__ = [
    "SkillsListInput",
    "SkillsLoadInput",
    "SkillsQueryOutput",
    "SkillsSearchInput",
    "SkillRegistry",
    "skills_list",
    "skills_list_sync",
    "skills_load",
    "skills_load_sync",
    "skills_search",
    "skills_search_sync",
]
