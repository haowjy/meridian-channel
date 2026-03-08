"""Skill operations."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from meridian.lib.config.skill_registry import SkillRegistry
from meridian.lib.domain import SkillContent, SkillManifest
from meridian.lib.formatting import FormatContext


class SkillsListInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    repo_root: str | None = None


class SkillsSearchInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    query: str = ""
    repo_root: str | None = None


class SkillsLoadInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = ""
    repo_root: str | None = None


class SkillsQueryOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    skills: tuple[SkillManifest, ...]

    def format_text(self, ctx: FormatContext | None = None) -> str:
        """One skill per line: name + description for text output mode."""
        if not self.skills:
            return "(no skills)"
        from meridian.cli.format_helpers import tabular

        return tabular([[skill.name, skill.description] for skill in self.skills])


def _registry(repo_root: str | None, *, readonly: bool = False) -> SkillRegistry:
    root = Path(repo_root).expanduser().resolve() if repo_root else None
    return SkillRegistry(repo_root=root, readonly=readonly)

def skills_list_sync(payload: SkillsListInput) -> SkillsQueryOutput:
    registry = _registry(payload.repo_root, readonly=True)
    return SkillsQueryOutput(skills=tuple(registry.list()))


def skills_search_sync(payload: SkillsSearchInput) -> SkillsQueryOutput:
    registry = _registry(payload.repo_root, readonly=True)
    return SkillsQueryOutput(skills=tuple(registry.search(payload.query)))


def skills_load_sync(payload: SkillsLoadInput) -> SkillContent:
    name = payload.name.strip()
    if not name:
        raise ValueError("Skill name must not be empty.")
    registry = _registry(payload.repo_root, readonly=True)
    return registry.show(name)


async def skills_list(payload: SkillsListInput) -> SkillsQueryOutput:
    return skills_list_sync(payload)


async def skills_search(payload: SkillsSearchInput) -> SkillsQueryOutput:
    return skills_search_sync(payload)


async def skills_load(payload: SkillsLoadInput) -> SkillContent:
    return skills_load_sync(payload)
