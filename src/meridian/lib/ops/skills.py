"""Skill operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from meridian.lib.config.skill_registry import SkillRegistry
from meridian.lib.domain import IndexReport, SkillContent, SkillManifest
from meridian.lib.ops.registry import OperationSpec, operation

if TYPE_CHECKING:
    from meridian.lib.formatting import FormatContext


@dataclass(frozen=True, slots=True)
class SkillsListInput:
    repo_root: str | None = None


@dataclass(frozen=True, slots=True)
class SkillsSearchInput:
    query: str = ""
    repo_root: str | None = None


@dataclass(frozen=True, slots=True)
class SkillsLoadInput:
    name: str = ""
    repo_root: str | None = None


@dataclass(frozen=True, slots=True)
class SkillsReindexInput:
    repo_root: str | None = None


@dataclass(frozen=True, slots=True)
class SkillsQueryOutput:
    skills: tuple[SkillManifest, ...]

    def format_text(self, ctx: FormatContext | None = None) -> str:
        """One skill per line: name + description for text output mode."""
        if not self.skills:
            return "(no skills)"
        from meridian.cli.format_helpers import tabular

        return tabular([[skill.name, skill.description] for skill in self.skills])


def _registry(repo_root: str | None) -> SkillRegistry:
    root = Path(repo_root).expanduser().resolve() if repo_root else None
    return SkillRegistry(repo_root=root)


def _ensure_index(registry: SkillRegistry) -> None:
    if not registry.list():
        registry.reindex()


def skills_list_sync(payload: SkillsListInput) -> SkillsQueryOutput:
    registry = _registry(payload.repo_root)
    _ensure_index(registry)
    return SkillsQueryOutput(skills=tuple(registry.list()))


def skills_search_sync(payload: SkillsSearchInput) -> SkillsQueryOutput:
    registry = _registry(payload.repo_root)
    _ensure_index(registry)
    return SkillsQueryOutput(skills=tuple(registry.search(payload.query)))


def skills_load_sync(payload: SkillsLoadInput) -> SkillContent:
    name = payload.name.strip()
    if not name:
        raise ValueError("Skill name must not be empty.")
    registry = _registry(payload.repo_root)
    _ensure_index(registry)
    return registry.show(name)


def skills_reindex_sync(payload: SkillsReindexInput) -> IndexReport:
    return _registry(payload.repo_root).reindex()


async def skills_list(payload: SkillsListInput) -> SkillsQueryOutput:
    return skills_list_sync(payload)


async def skills_search(payload: SkillsSearchInput) -> SkillsQueryOutput:
    return skills_search_sync(payload)


async def skills_load(payload: SkillsLoadInput) -> SkillContent:
    return skills_load_sync(payload)


async def skills_reindex(payload: SkillsReindexInput) -> IndexReport:
    return skills_reindex_sync(payload)


operation(
    OperationSpec[SkillsSearchInput, SkillsQueryOutput](
        name="skills.search",
        handler=skills_search,
        sync_handler=skills_search_sync,
        input_type=SkillsSearchInput,
        output_type=SkillsQueryOutput,
        cli_group="skills",
        cli_name="search",
        mcp_name="skills_search",
        description="Search skills by keyword/tag.",
    )
)

operation(
    OperationSpec[SkillsLoadInput, SkillContent](
        name="skills.load",
        handler=skills_load,
        sync_handler=skills_load_sync,
        input_type=SkillsLoadInput,
        output_type=SkillContent,
        cli_group="skills",
        cli_name="show",
        mcp_name="skills_load",
        description="Load full SKILL.md content for a skill.",
    )
)

operation(
    OperationSpec[SkillsListInput, SkillsQueryOutput](
        name="skills.list",
        handler=skills_list,
        sync_handler=skills_list_sync,
        input_type=SkillsListInput,
        output_type=SkillsQueryOutput,
        cli_group="skills",
        cli_name="list",
        mcp_name="skills_list",
        description="List all indexed skills.",
    )
)

operation(
    OperationSpec[SkillsReindexInput, IndexReport](
        name="skills.reindex",
        handler=skills_reindex,
        sync_handler=skills_reindex_sync,
        input_type=SkillsReindexInput,
        output_type=IndexReport,
        cli_group="skills",
        cli_name="reindex",
        mcp_name="skills_reindex",
        description="Reindex skills from .agents/skills.",
    )
)
