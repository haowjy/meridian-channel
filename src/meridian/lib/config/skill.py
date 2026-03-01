"""SKILL.md parsing and scanning."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from meridian.lib.config._paths import resolve_path_list, resolve_repo_root
from meridian.lib.config.settings import load_config

_INT_RE = re.compile(r"^-?[0-9]+$")
_FLOAT_RE = re.compile(r"^-?(?:[0-9]+\.[0-9]*|\.[0-9]+)$")
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


@dataclass(frozen=True, slots=True)
class SkillDocument:
    """Parsed representation of one SKILL.md file."""

    name: str
    description: str
    tags: tuple[str, ...]
    path: Path
    content: str
    body: str
    frontmatter: dict[str, object]


def _split_inline_list_items(raw: str) -> list[str]:
    items: list[str] = []
    current: list[str] = []
    quote: str | None = None

    for char in raw:
        if quote is not None:
            if char == quote:
                quote = None
            else:
                current.append(char)
            continue

        if char in {'"', "'"}:
            quote = char
            continue
        if char == ",":
            items.append("".join(current).strip())
            current = []
            continue
        current.append(char)

    items.append("".join(current).strip())
    return [item for item in items if item]


def _parse_scalar(raw: str) -> object:
    value = raw.strip()
    if not value:
        return ""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]

    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    if _INT_RE.fullmatch(value):
        return int(value)
    if _FLOAT_RE.fullmatch(value):
        return float(value)
    return value


def _parse_value(raw: str) -> object:
    value = raw.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part) for part in _split_inline_list_items(inner)]
    return _parse_scalar(value)


def parse_frontmatter(frontmatter_text: str) -> dict[str, object]:
    """Parse a constrained YAML frontmatter subset used by SKILL.md and agents."""

    parsed: dict[str, object] = {}
    lines = frontmatter_text.splitlines()
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            index += 1
            continue
        if ":" not in line:
            index += 1
            continue

        key_text, value_text = line.split(":", 1)
        key = key_text.strip()
        value = value_text.strip()
        if not key:
            index += 1
            continue

        if value:
            parsed[key] = _parse_value(value)
            index += 1
            continue

        items: list[object] = []
        next_index = index + 1
        while next_index < len(lines):
            next_line = lines[next_index]
            next_stripped = next_line.strip()
            if not next_stripped:
                next_index += 1
                continue
            left_trimmed = next_line.lstrip()
            if left_trimmed.startswith("- "):
                items.append(_parse_scalar(left_trimmed[2:].strip()))
                next_index += 1
                continue
            break

        if items:
            parsed[key] = items
            index = next_index
        else:
            parsed[key] = ""
            index += 1

    return parsed


def split_markdown_frontmatter(markdown: str) -> tuple[dict[str, object], str]:
    """Split markdown into YAML frontmatter and body."""

    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, markdown

    frontmatter_end = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            frontmatter_end = index
            break

    if frontmatter_end is None:
        return {}, markdown

    frontmatter = parse_frontmatter("\n".join(lines[1:frontmatter_end]))
    body_lines = lines[frontmatter_end + 1 :]
    body = "\n".join(body_lines)
    if markdown.endswith("\n"):
        body = f"{body}\n"
    return frontmatter, body


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
