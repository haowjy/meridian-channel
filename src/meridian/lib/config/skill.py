"""SKILL.md parsing and scanning."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict

from meridian.lib.config._paths import resolve_path_list, resolve_repo_root
from meridian.lib.config.settings import load_config

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class SkillDocument(BaseModel):
    """Parsed representation of one SKILL.md file."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    tags: tuple[str, ...]
    path: Path
    content: str
    body: str
    frontmatter: dict[str, object]


def split_markdown_frontmatter(markdown: str) -> tuple[dict[str, object], str]:
    """Split markdown into YAML frontmatter and body."""
    import frontmatter  # type: ignore[import-untyped]
    import yaml

    try:
        post = frontmatter.loads(markdown)
    except yaml.YAMLError:
        logger.warning("Malformed YAML frontmatter, treating as plain markdown")
        return {}, markdown
    return dict(post.metadata), post.content


def _coerce_string_list(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        candidate = value.strip()
        return (candidate,) if candidate else ()
    if isinstance(value, list):
        normalized = [
            str(item).strip()
            for item in cast("list[object]", value)
            if str(item).strip()
        ]
        return tuple(normalized)
    return ()


def parse_skill_file(path: Path) -> SkillDocument:
    """Parse one SKILL.md file."""

    content = path.read_text(encoding="utf-8")
    frontmatter, body = split_markdown_frontmatter(content)

    name_value = frontmatter.get("name")
    description_value = frontmatter.get("description")
    tags_value = frontmatter.get("tags")

    name = str(name_value).strip() if name_value is not None else path.parent.name
    description = str(description_value).strip() if description_value is not None else ""
    tags = _coerce_string_list(tags_value)

    return SkillDocument(
        name=name or path.parent.name,
        description=description,
        tags=tags,
        path=path.resolve(),
        content=content,
        body=body,
        frontmatter=frontmatter,
    )


def discover_skill_files(skills_dir: Path) -> list[Path]:
    """Discover all SKILL.md files under `.agents/skills/`."""

    if not skills_dir.is_dir():
        return []
    return sorted(path for path in skills_dir.rglob("SKILL.md") if path.is_file())


def _skill_search_dirs(repo_root: Path) -> list[Path]:
    config = load_config(repo_root).search_paths
    return resolve_path_list(
        config.skills,
        config.global_skills,
        repo_root,
    )


def _files_have_equal_text(first: Path, second: Path) -> bool:
    try:
        return first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")
    except OSError:
        return False


def scan_skills(
    repo_root: Path | None = None,
    skills_dirs: list[Path] | None = None,
) -> list[SkillDocument]:
    """Scan configured skill directories and parse all discovered skills."""

    root = resolve_repo_root(repo_root)
    directories = skills_dirs if skills_dirs is not None else _skill_search_dirs(root)
    documents: list[SkillDocument] = []
    selected_by_name: dict[str, SkillDocument] = {}

    for directory in directories:
        for path in discover_skill_files(directory):
            document = parse_skill_file(path)
            existing = selected_by_name.get(document.name)
            if existing is not None:
                if _files_have_equal_text(existing.path, document.path):
                    continue
                logger.warning(
                    "Skill '%s' found in multiple paths with conflicting content: %s, %s. "
                    "Using %s; conflicting duplicate ignored.",
                    document.name,
                    existing.path,
                    document.path,
                    existing.path,
                )
                continue
            selected_by_name[document.name] = document
            documents.append(document)
    return documents
