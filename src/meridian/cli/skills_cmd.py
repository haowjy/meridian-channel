"""CLI command handlers for skills.* operations."""


from collections.abc import Callable
from functools import partial
from typing import Any

from meridian.cli.registration import register_manifest_cli_group
from meridian.lib.ops.catalog import (
    SkillsListInput,
    SkillsLoadInput,
    SkillsSearchInput,
    skills_list_sync,
    skills_load_sync,
    skills_search_sync,
)

Emitter = Callable[[Any], None]


def _skills_list(emit: Emitter) -> None:
    emit(skills_list_sync(SkillsListInput()))


def _skills_search(emit: Emitter, query: str = "") -> None:
    emit(skills_search_sync(SkillsSearchInput(query=query)))


def _skills_show(emit: Emitter, name: str) -> None:
    emit(skills_load_sync(SkillsLoadInput(name=name)))


def register_skills_commands(app: Any, emit: Emitter) -> tuple[set[str], dict[str, str]]:
    handlers: dict[str, Callable[[], Callable[..., None]]] = {
        "skills.list": lambda: partial(_skills_list, emit),
        "skills.search": lambda: partial(_skills_search, emit),
        "skills.show": lambda: partial(_skills_show, emit),
    }
    return register_manifest_cli_group(app, group="skills", handlers=handlers)
