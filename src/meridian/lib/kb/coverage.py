"""Source-file coverage analysis for KB documents."""

from __future__ import annotations

import os
from pathlib import Path

from meridian.lib.kb.types import CoverageResult, GraphNode, SymbolEdge
from meridian.lib.platform import IS_WINDOWS

# Default source file extensions
DEFAULT_SOURCE_EXTS = (".py", ".rs", ".ts", ".go", ".js")

# Directories to skip when walking source trees
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox", "dist", "build"}


def compute_coverage(
    nodes: dict[Path, GraphNode],
    source_dirs: list[Path],
    source_exts: list[str] | None = None,
    resolve_symbols: bool = False,
) -> CoverageResult:
    """Compute source-file coverage from KB documents.

    A source file is "covered" if any suffix of its path appears in any
    markdown document's link targets, inline code content, or fenced block content.

    Args:
        nodes: Dict of markdown documents keyed by path
        source_dirs: Directories to scan for source files
        source_exts: File extensions to include (default: .py, .rs, .ts, .go, .js)
        resolve_symbols: Whether to use AST to resolve Python symbols

    Returns:
        CoverageResult with covered/uncovered files and optional symbol edges
    """
    exts = tuple(source_exts) if source_exts else DEFAULT_SOURCE_EXTS

    # Build mention corpus from all markdown documents
    corpus = _build_mention_corpus(nodes)

    # Collect source files
    source_files: list[Path] = []
    for source_dir in source_dirs:
        source_files.extend(_collect_source_files(source_dir, exts))

    # Check coverage for each source file
    covered: list[tuple[Path, float]] = []
    uncovered: list[Path] = []

    for src_file in source_files:
        match_confidence = _check_coverage(src_file, corpus, source_dirs)
        if match_confidence > 0:
            covered.append((src_file, match_confidence))
        else:
            uncovered.append(src_file)

    # Symbol resolution (optional)
    symbol_edges: list[SymbolEdge] = []
    if resolve_symbols:
        symbol_edges = _resolve_symbols(nodes, source_dirs, exts)

    return CoverageResult(
        covered=covered,
        uncovered=uncovered,
        source_roots=source_dirs,
        symbol_edges=symbol_edges,
    )


def _build_mention_corpus(nodes: dict[Path, GraphNode]) -> set[str]:
    """Build a set of all strings that might reference source files.

    Includes: link targets, fenced block content, and inline text that
    might contain path mentions.
    """
    corpus: set[str] = set()

    for node in nodes.values():
        doc = node.doc
        if doc.error:
            continue

        # Add link targets
        for ref in doc.references:
            target = ref.target
            # Normalize to forward slashes for cross-platform comparison
            normalized = target.replace("\\", "/")
            corpus.add(normalized)
            # Also add without extension for flexibility
            if "." in normalized:
                corpus.add(normalized.rsplit(".", 1)[0])

        # Add fenced block content (may contain file paths)
        for block in doc.fenced_blocks:
            # Add each line that looks like a path
            for line in block.content.split("\n"):
                line = line.strip()
                if line:
                    normalized = line.replace("\\", "/")
                    corpus.add(normalized)

    return corpus


def _collect_source_files(root: Path, exts: tuple[str, ...]) -> list[Path]:
    """Walk directory and collect source files with matching extensions."""
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skipped directories in-place
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for filename in filenames:
            if any(filename.endswith(ext) for ext in exts):
                files.append(Path(dirpath) / filename)
    return sorted(files)


def _check_coverage(
    src_file: Path, corpus: set[str], source_roots: list[Path]
) -> float:
    """Check if a source file is mentioned in the corpus.

    Returns confidence score (0.0 = not covered, 1.0 = exact match).
    """
    # Try different path representations
    paths_to_check: list[str] = []

    # Absolute path (normalized)
    paths_to_check.append(src_file.as_posix())

    # Relative to each source root
    for root in source_roots:
        try:
            rel = src_file.relative_to(root).as_posix()
            paths_to_check.append(rel)
            # Also without extension
            if "." in rel:
                paths_to_check.append(rel.rsplit(".", 1)[0])
        except ValueError:
            pass

    # Just the filename
    paths_to_check.append(src_file.name)

    # Check if any suffix appears in corpus
    for path_str in paths_to_check:
        if _matches_corpus(path_str, corpus):
            return 1.0

    return 0.0


def _matches_corpus(path_str: str, corpus: set[str]) -> bool:
    """Check if path_str or any of its suffixes appear in corpus."""
    # Normalize path separators
    normalized = path_str.replace("\\", "/")

    # Case sensitivity depends on platform
    if IS_WINDOWS:
        normalized_lower = normalized.lower()
        corpus_lower = {s.lower() for s in corpus}
        return normalized_lower in corpus_lower or any(
            s.endswith(normalized_lower) or normalized_lower.endswith(s)
            for s in corpus_lower
        )
    else:
        return normalized in corpus or any(
            s.endswith(normalized) or normalized.endswith(s) for s in corpus
        )


def _resolve_symbols(
    nodes: dict[Path, GraphNode],
    source_dirs: list[Path],
    exts: tuple[str, ...],
) -> list[SymbolEdge]:
    """Resolve symbol references from markdown to source code.

    Uses symbol_resolver to parse Python files and match against
    inline code mentions in markdown.
    """
    from meridian.lib.kb.symbol_resolver import PythonSymbolResolver

    resolver = PythonSymbolResolver()
    edges: list[SymbolEdge] = []

    # Build symbol index from Python files
    symbol_index: dict[str, list[tuple[Path, int]]] = {}  # symbol_name -> [(file, line), ...]

    for source_dir in source_dirs:
        for src_file in _collect_source_files(source_dir, exts):
            if not resolver.can_handle(src_file):
                continue
            symbols = resolver.resolve(src_file)
            for name, line in symbols:
                if name not in symbol_index:
                    symbol_index[name] = []
                symbol_index[name].append((src_file, line))

    # Check markdown documents for symbol mentions
    for doc_path, node in nodes.items():
        doc = node.doc
        if doc.error:
            continue

        # Check references for symbol-like targets
        for ref in doc.references:
            target = ref.target
            # Extract potential symbol name (last path component without extension)
            if "/" in target or "\\" in target:
                continue  # Skip path-like targets
            if target in symbol_index:
                for src_file, line in symbol_index[target]:
                    edges.append(
                        SymbolEdge(
                            doc_path=doc_path,
                            src_file=src_file,
                            symbol_name=target,
                            symbol_line=line,
                        )
                    )

    return edges


__all__ = ["compute_coverage"]
