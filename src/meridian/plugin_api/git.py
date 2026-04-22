"""Plugin-facing Git URL and clone-path helpers."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from meridian.plugin_api.config import get_git_overrides
from meridian.plugin_api.state import get_user_home

_SSH_URL_RE = re.compile(r"^git@([^:]+):(.+?)(?:\.git)?$")
_NON_SLUG_CHAR_RE = re.compile(r"[^a-zA-Z0-9-]")


def generate_repo_slug(repo_url: str) -> str:
    """Generate a filesystem-safe slug from a remote URL."""

    ssh_match = _SSH_URL_RE.match(repo_url)
    if ssh_match:
        path = ssh_match.group(2)
        return path.replace("/", "-").lower()

    parsed = urlparse(repo_url)
    if parsed.scheme in {"http", "https"}:
        path = parsed.path.strip("/").removesuffix(".git")
        return path.replace("/", "-").lower()

    return _NON_SLUG_CHAR_RE.sub("-", repo_url).lower()[:100]


def normalize_repo_url(url: str) -> str:
    """Normalize a Git URL for override comparison."""

    return url.rstrip("/").removesuffix(".git")


def resolve_clone_path(repo_url: str) -> Path:
    """Resolve local clone path for a repository URL.

    Priority:
    1. ``[git."<url>"].path`` override from user config
    2. ``<meridian_home>/git/<generated-slug>``
    """

    normalized_repo_url = normalize_repo_url(repo_url)
    overrides = get_git_overrides()

    for override_url, override_config in overrides.items():
        if normalize_repo_url(override_url) != normalized_repo_url:
            continue
        override_path = override_config.get("path")
        if override_path:
            return Path(override_path).expanduser().resolve()

    return (get_user_home() / "git" / generate_repo_slug(repo_url)).resolve()
