"""Agent profile parser for `.agents/agents/*.md`."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from meridian.lib.config._paths import resolve_path_list, resolve_repo_root
from meridian.lib.config.settings import SearchPathConfig, load_config
from meridian.lib.config.skill import split_markdown_frontmatter

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Sentinel path used for built-in profiles that don't exist on disk.
_BUILTIN_PATH = Path("<builtin>")


@dataclass(frozen=True, slots=True)
class AgentProfile:
    """Parsed agent profile with frontmatter defaults + markdown body."""

    name: str
    description: str
    model: str | None
    variant: str | None
    skills: tuple[str, ...]
    tools: tuple[str, ...]
    mcp_tools: tuple[str, ...]
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
        mcp_tools=_normalize_string_list(frontmatter.get("mcp-tools")),
        sandbox=str(sandbox_value).strip() if sandbox_value is not None else None,
        variant_models=_normalize_string_list(frontmatter.get("variant-models")),
        body=body,
        path=path.resolve(),
    )


def _builtin_profiles() -> dict[str, AgentProfile]:
    """Hard-coded fallback profiles used when no file exists on disk."""
    return {
        "agent": AgentProfile(
            name="agent",
            description="Default agent",
            model="gpt-5.3-codex",
            variant=None,
            skills=("run-agent", "agent"),
            tools=(),
            mcp_tools=("run_list", "run_show", "skills_list"),
            sandbox="workspace-write",
            variant_models=(),
            body="",
            path=_BUILTIN_PATH,
        ),
        "supervisor": AgentProfile(
            name="supervisor",
            description="Workspace supervisor",
            model="claude-opus-4-6",
            variant=None,
            skills=("run-agent", "agent", "orchestrate"),
            tools=(),
            mcp_tools=(
                "run_create",
                "run_list",
                "run_show",
                "run_wait",
                "skills_list",
                "models_list",
            ),
            sandbox="unrestricted",
            variant_models=(),
            body="",
            path=_BUILTIN_PATH,
        ),
    }


def _agent_search_dirs(
    repo_root: Path,
    search_paths: SearchPathConfig | None = None,
) -> list[Path]:
    config_paths = search_paths or load_config(repo_root).search_paths
    return resolve_path_list(
        config_paths.agents,
        config_paths.global_agents,
        repo_root,
    )


def scan_agent_profiles(
    repo_root: Path | None = None,
    search_dirs: list[Path] | None = None,
    *,
    search_paths: SearchPathConfig | None = None,
) -> list[AgentProfile]:
    """Parse all agent profiles from configured search directories."""

    root = resolve_repo_root(repo_root)
    directories = (
        search_dirs
        if search_dirs is not None
        else _agent_search_dirs(root, search_paths=search_paths)
    )
    profiles: list[AgentProfile] = []
    selected_by_name: dict[str, AgentProfile] = {}

    for directory in directories:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            profile = parse_agent_profile(path)
            existing = selected_by_name.get(profile.name)
            if existing is not None:
                logger.warning(
                    "Agent profile '%s' found in multiple paths: %s, %s. Using %s.",
                    profile.name,
                    existing.path,
                    profile.path,
                    existing.path,
                )
                continue
            selected_by_name[profile.name] = profile
            profiles.append(profile)
    return profiles


def load_agent_profile(
    name: str,
    repo_root: Path | None = None,
    *,
    search_paths: SearchPathConfig | None = None,
) -> AgentProfile:
    """Load one agent profile by filename stem or frontmatter name."""

    normalized = name.strip()
    if not normalized:
        raise ValueError("Agent profile name must not be empty.")

    for profile in scan_agent_profiles(repo_root=repo_root, search_paths=search_paths):
        if profile.path.stem == normalized or profile.name == normalized:
            return profile

    # Fall back to hard-coded built-in profiles.
    builtin = _builtin_profiles().get(normalized)
    if builtin is not None:
        logger.info("Using built-in profile '%s' (no file found on disk).", normalized)
        return builtin

    raise FileNotFoundError(f"Agent profile '{name}' not found in configured search paths.")
