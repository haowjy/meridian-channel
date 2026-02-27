"""SQLite-backed skill index and retrieval."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from meridian.lib.config._paths import (
    bundled_agents_root,
    default_index_db_path,
    resolve_path_list,
    resolve_repo_root,
)
from meridian.lib.config.settings import SearchPathConfig, load_config
from meridian.lib.config.skill import SkillDocument, scan_skills
from meridian.lib.domain import IndexReport, SkillContent, SkillManifest
from meridian.lib.state.db import DEFAULT_BUSY_TIMEOUT_MS

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS skills (
    name TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    tags_json TEXT NOT NULL,
    content TEXT NOT NULL,
    path TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_skills_description ON skills(description);
"""


@dataclass(frozen=True, slots=True)
class SkillRow:
    """Internal row representation from SQLite."""

    name: str
    description: str
    tags: tuple[str, ...]
    content: str
    path: str


class SkillRegistry:
    """Skill catalog with discovery + indexing from configured skill directories."""

    def __init__(
        self,
        db_path: Path | None = None,
        repo_root: Path | None = None,
        *,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
        search_paths: SearchPathConfig | None = None,
        readonly: bool = False,
    ) -> None:
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
        self._db_path = (db_path or default_index_db_path(self._repo_root)).resolve()
        self._busy_timeout_ms = busy_timeout_ms
        self._readonly = readonly
        self._filesystem_documents: tuple[SkillDocument, ...] | None = None
        if not self._readonly:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._ensure_schema()

    @property
    def db_path(self) -> Path:
        return self._db_path

    @property
    def repo_root(self) -> Path:
        return self._repo_root

    @property
    def skills_dirs(self) -> tuple[Path, ...]:
        return self._skills_dirs

    @property
    def readonly(self) -> bool:
        return self._readonly

    def _scan_documents(self, *, refresh: bool = False) -> tuple[SkillDocument, ...]:
        if self._filesystem_documents is None or refresh:
            self._filesystem_documents = tuple(
                scan_skills(self._repo_root, skills_dirs=list(self._skills_dirs))
            )
        return self._filesystem_documents

    def _connect(self) -> sqlite3.Connection:
        if self._readonly:
            raise RuntimeError("SkillRegistry opened in readonly filesystem mode.")
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(f"PRAGMA busy_timeout = {self._busy_timeout_ms}")
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(_SCHEMA_SQL)

    def reindex(self, skills_dir: Path | None = None) -> IndexReport:
        """Rebuild index from configured skill search directories."""

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

        documents = scan_skills(self._repo_root, skills_dirs=scan_dirs)
        if self._readonly:
            self._filesystem_documents = tuple(documents)
            return IndexReport(indexed_count=len(documents))
        with self._connect() as connection:
            connection.execute("DELETE FROM skills")
            connection.executemany(
                """
                INSERT INTO skills(name, description, tags_json, content, path)
                VALUES(?, ?, ?, ?, ?)
                """,
                [
                    (
                        doc.name,
                        doc.description,
                        json.dumps(doc.tags),
                        doc.content,
                        str(doc.path),
                    )
                    for doc in documents
                ],
            )
        return IndexReport(indexed_count=len(documents))

    def _read_rows(self, query: str, params: tuple[object, ...] = ()) -> list[SkillRow]:
        with self._connect() as connection:
            cursor = connection.execute(query, params)
            rows = cursor.fetchall()
        return [
            SkillRow(
                name=str(row["name"]),
                description=str(row["description"]),
                tags=tuple(str(item) for item in json.loads(str(row["tags_json"]))),
                content=str(row["content"]),
                path=str(row["path"]),
            )
            for row in rows
        ]

    def list(self) -> list[SkillManifest]:
        """List all indexed skills."""

        if self._readonly:
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

        rows = self._read_rows(
            "SELECT name, description, tags_json, content, path FROM skills ORDER BY name ASC"
        )
        return [
            SkillManifest(name=row.name, description=row.description, tags=row.tags, path=row.path)
            for row in rows
        ]

    def search(self, query: str) -> list[SkillManifest]:
        """Keyword search against name/description/tags/content."""

        normalized = query.strip().lower()
        if not normalized:
            return self.list()

        if self._readonly:
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

        like = f"%{normalized}%"
        rows = self._read_rows(
            """
            SELECT name, description, tags_json, content, path
            FROM skills
            WHERE lower(name) LIKE ?
               OR lower(description) LIKE ?
               OR lower(tags_json) LIKE ?
               OR lower(content) LIKE ?
            ORDER BY name ASC
            """,
            (like, like, like, like),
        )
        return [
            SkillManifest(name=row.name, description=row.description, tags=row.tags, path=row.path)
            for row in rows
        ]

    def load(self, names: list[str]) -> list[SkillContent]:
        """Load full SKILL.md content for specific skill names in requested order."""

        normalized_names = [name.strip() for name in names if name.strip()]
        if not normalized_names:
            return []

        if self._readonly:
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

        loaded_by_name: dict[str, SkillContent] = {}
        placeholders = ", ".join("?" for _ in normalized_names)
        rows = self._read_rows(
            f"""
            SELECT name, description, tags_json, content, path
            FROM skills
            WHERE name IN ({placeholders})
            """,
            tuple(normalized_names),
        )
        for row in rows:
            loaded_by_name[row.name] = SkillContent(
                name=row.name,
                description=row.description,
                tags=row.tags,
                content=row.content,
                path=row.path,
            )

        missing = [name for name in normalized_names if name not in loaded_by_name]
        if missing:
            raise KeyError(f"Unknown skills: {', '.join(missing)}")
        return [loaded_by_name[name] for name in normalized_names]

    def show(self, name: str) -> SkillContent:
        """Load one skill content payload by name."""

        loaded = self.load([name])
        return loaded[0]
