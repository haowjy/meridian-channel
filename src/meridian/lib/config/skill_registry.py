"""Filesystem-backed skill catalog and retrieval."""

from __future__ import annotations

from pathlib import Path

from meridian.lib.config._paths import bundled_agents_root, resolve_path_list, resolve_repo_root
from meridian.lib.config.settings import SearchPathConfig, load_config
from meridian.lib.config.skill import SkillDocument, scan_skills
from meridian.lib.domain import IndexReport, SkillContent, SkillManifest


class SkillRegistry:
    """Skill catalog with discovery from configured skill directories."""

    def __init__(
        self,
        db_path: Path | None = None,
        repo_root: Path | None = None,
        *,
        busy_timeout_ms: int = 0,
        search_paths: SearchPathConfig | None = None,
        readonly: bool = False,
    ) -> None:
        _ = db_path
        _ = busy_timeout_ms
        self._repo_root = resolve_repo_root(repo_root)
        resolved_search_paths = search_paths or load_config(self._repo_root).search_paths
        resolved_skills_dirs = resolve_path_list(
            resolved_search_paths.skills,
            resolved_search_paths.global_skills,
            self._repo_root,
        )
        bundled_root = bundled_agents_root()
        if bundled_root is not None:
            bundled_skills_dir = bundled_root / "skills"
            if bundled_skills_dir.is_dir() and bundled_skills_dir not in resolved_skills_dirs:
                resolved_skills_dirs.append(bundled_skills_dir)

        self._skills_dirs = tuple(resolved_skills_dirs)
        self._readonly = readonly
        self._filesystem_documents: tuple[SkillDocument, ...] | None = None

    @property
    def repo_root(self) -> Path:
        return self._repo_root

    @property
    def skills_dirs(self) -> tuple[Path, ...]:
        return self._skills_dirs

    @property
    def readonly(self) -> bool:
        return self._readonly

    @property
    def db_path(self) -> Path:
        return self._repo_root / ".meridian" / "index" / "skills.json"

    def _scan_documents(self, *, refresh: bool = False) -> tuple[SkillDocument, ...]:
        if self._filesystem_documents is None or refresh:
            self._filesystem_documents = tuple(
                scan_skills(self._repo_root, skills_dirs=list(self._skills_dirs))
            )
        return self._filesystem_documents

    def reindex(self, skills_dir: Path | None = None) -> IndexReport:
        """Refresh in-memory index from configured skill search directories."""

        scan_dirs: list[Path]
        if skills_dir is not None:
            requested = skills_dir.resolve()
            if requested not in self._skills_dirs:
                expected = ", ".join(path.as_posix() for path in self._skills_dirs)
                expected_text = expected if expected else "<none>"
                raise ValueError(
                    "Skill discovery is restricted to configured search paths; "
                    f"expected one of '{expected_text}', got '{skills_dir}'."
                )
            scan_dirs = [requested]
        else:
            scan_dirs = list(self._skills_dirs)

        documents = tuple(scan_skills(self._repo_root, skills_dirs=scan_dirs))
        self._filesystem_documents = documents
        return IndexReport(indexed_count=len(documents))

    def list(self) -> list[SkillManifest]:
        """List all discovered skills."""

        return sorted(
            [
                SkillManifest(
                    name=document.name,
                    description=document.description,
                    tags=document.tags,
                    path=str(document.path),
                )
                for document in self._scan_documents()
            ],
            key=lambda item: item.name,
        )

    def search(self, query: str) -> list[SkillManifest]:
        """Keyword search against name/description/tags/content."""

        normalized = query.strip().lower()
        if not normalized:
            return self.list()

        return sorted(
            [
                SkillManifest(
                    name=document.name,
                    description=document.description,
                    tags=document.tags,
                    path=str(document.path),
                )
                for document in self._scan_documents()
                if normalized in document.name.lower()
                or normalized in document.description.lower()
                or normalized in " ".join(document.tags).lower()
                or normalized in document.content.lower()
            ],
            key=lambda item: item.name,
        )

    def load(self, names: list[str]) -> list[SkillContent]:
        """Load full SKILL.md content for specific skill names in requested order."""

        normalized_names = [name.strip() for name in names if name.strip()]
        if not normalized_names:
            return []

        docs_by_name = {document.name: document for document in self._scan_documents()}
        missing = [name for name in normalized_names if name not in docs_by_name]
        if missing:
            raise KeyError(f"Unknown skills: {', '.join(missing)}")

        return [
            SkillContent(
                name=docs_by_name[name].name,
                description=docs_by_name[name].description,
                tags=docs_by_name[name].tags,
                content=docs_by_name[name].content,
                path=str(docs_by_name[name].path),
            )
            for name in normalized_names
        ]

    def show(self, name: str) -> SkillContent:
        """Load one skill content payload by name."""

        loaded = self.load([name])
        return loaded[0]
