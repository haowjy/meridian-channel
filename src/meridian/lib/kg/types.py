"""Typed models for KG graph analysis.

These types are KG-specific. Extraction types live in lib/markdown/types.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from meridian.lib.markdown.types import ExtractedDocument


@dataclass
class GraphNode:
    """One document in the knowledge graph."""

    doc: ExtractedDocument
    rel_path: str  # path relative to root (display key), forward slashes
    in_degree: int = 0  # count of inbound links (computed)


@dataclass
class GraphEdge:
    """Directed edge in the document graph."""

    src: Path  # source document
    dst: Path | str  # resolved Path for local links; raw str for wikilinks/unresolved
    kind: str  # "md_link" | "image" | "wikilink"
    resolved: bool  # True if dst exists on filesystem
    line: int  # source line number


@dataclass
class AnalysisResult:
    """Complete KG analysis output."""

    nodes: dict[Path, GraphNode] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)
    broken_links: list[GraphEdge] = field(default_factory=list)
    orphans: list[Path] = field(default_factory=list)
    missing_backlinks: list[tuple[Path, Path]] = field(default_factory=list)
    clusters: list[list[Path]] = field(default_factory=list)


__all__ = [
    "AnalysisResult",
    "GraphEdge",
    "GraphNode",
]
