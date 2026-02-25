"""Agent profile parser for `.agents/agents/*.md`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from meridian.lib.config._paths import canonical_agents_dir, resolve_repo_root
from meridian.lib.config.skill import split_markdown_frontmatter


@dataclass(frozen=True, slots=True)
class AgentProfile:
    """Parsed agent profile with frontmatter defaults + markdown body."""

    name: str
    description: str
    model: str | None
    variant: str | None
    skills: tuple[str, ...]
    tools: tuple[str, ...]
    sandbox: str | None
    variant_models: tuple[str, ...]
    body: str
    path: Path


def _normalize_string_list(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        normalized = value.strip()
        return (normalized,) if normalized else ()
    if isinstance(value, list):
        values = [
            str(item).strip()
            for item in cast("list[object]", value)
            if str(item).strip()
        ]
        return tuple(values)
    return ()


def parse_agent_profile(path: Path) -> AgentProfile:
    """Parse a single markdown agent profile file."""

    markdown = path.read_text(encoding="utf-8")
    frontmatter, body = split_markdown_frontmatter(markdown)

    name_value = frontmatter.get("name")
    description_value = frontmatter.get("description")
    model_value = frontmatter.get("model")
    variant_value = frontmatter.get("variant")
    sandbox_value = frontmatter.get("sandbox")

    return AgentProfile(
        name=str(name_value).strip() if name_value is not None else path.stem,
        description=str(description_value).strip() if description_value is not None else "",
        model=str(model_value).strip() if model_value is not None else None,
        variant=str(variant_value).strip() if variant_value is not None else None,
        skills=_normalize_string_list(frontmatter.get("skills")),
        tools=_normalize_string_list(frontmatter.get("tools")),
        sandbox=str(sandbox_value).strip() if sandbox_value is not None else None,
        variant_models=_normalize_string_list(frontmatter.get("variant-models")),
        body=body,
        path=path.resolve(),
    )


def scan_agent_profiles(repo_root: Path | None = None) -> list[AgentProfile]:
    """Parse all agent profiles under canonical `.agents/agents/`."""

    root = resolve_repo_root(repo_root)
    agents_dir = canonical_agents_dir(root)
    if not agents_dir.is_dir():
        return []
    return [parse_agent_profile(path) for path in sorted(agents_dir.glob("*.md"))]


def load_agent_profile(name: str, repo_root: Path | None = None) -> AgentProfile:
    """Load one agent profile by filename stem or frontmatter name."""

    normalized = name.strip()
    if not normalized:
        raise ValueError("Agent profile name must not be empty.")

    for profile in scan_agent_profiles(repo_root=repo_root):
        if profile.path.stem == normalized or profile.name == normalized:
            return profile
    raise FileNotFoundError(f"Agent profile '{name}' not found under .agents/agents/")
