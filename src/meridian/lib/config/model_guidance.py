"""Model guidance loader with override precedence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from meridian.lib.config._paths import resolve_repo_root


@dataclass(frozen=True, slots=True)
class ModelGuidanceBundle:
    """Loaded model-guidance content and source files."""

    content: str
    paths: tuple[Path, ...]


def _guidance_root(repo_root: Path) -> Path:
    return repo_root / ".agents" / "skills" / "run-agent" / "references"


def selected_guidance_paths(repo_root: Path | None = None) -> tuple[Path, ...]:
    """Select guidance files using custom-over-default precedence."""

    root = resolve_repo_root(repo_root)
    references_dir = _guidance_root(root)
    default_file = references_dir / "default-model-guidance.md"
    custom_dir = references_dir / "model-guidance"

    selected_custom = ()
    if custom_dir.is_dir():
        selected_custom = tuple(
            path
            for path in sorted(custom_dir.glob("*.md"))
            if path.is_file() and path.name != "README.md"
        )

    if selected_custom:
        return selected_custom
    if default_file.is_file():
        return (default_file,)
    raise FileNotFoundError(f"Default model guidance file not found: {default_file}")


def load_model_guidance(repo_root: Path | None = None) -> ModelGuidanceBundle:
    """Load model guidance markdown with override precedence."""

    paths = selected_guidance_paths(repo_root=repo_root)
    content = "\n\n".join(path.read_text(encoding="utf-8").strip() for path in paths).strip()
    return ModelGuidanceBundle(content=content, paths=paths)

