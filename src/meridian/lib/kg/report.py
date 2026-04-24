"""Plain-text report formatting for KG analysis results."""

from __future__ import annotations

from pathlib import Path

from meridian.lib.kg.types import AnalysisResult


def format_report(
    result: AnalysisResult,
    root: Path,
    *,
    targeted: bool = False,
) -> str:
    """Format AnalysisResult as plain-text report.

    Args:
        result: Analysis result to format
        root: Root path for relative path display
        targeted: If True, format as targeted check (single file/dir)

    Returns:
        Plain text report string
    """
    lines: list[str] = []

    # Header
    lines.append(f"## KG Analysis: {root.as_posix()}")
    lines.append(f"Files scanned: {len(result.nodes)}")
    lines.append(f"Total links: {len(result.edges)}")
    lines.append("")

    # Broken Links section
    lines.append("## Broken Links")
    if result.broken_links:
        for edge in result.broken_links:
            src_rel = _rel(edge.src, root)
            target_str = str(edge.dst) if isinstance(edge.dst, str) else _rel(edge.dst, root)
            lines.append(f"  {src_rel}:{edge.line} -> {target_str} [{edge.kind}]")
    else:
        lines.append("  None")
    lines.append("")

    # Orphaned Files section
    lines.append("## Orphaned Files")
    lines.append("  (Documents with no inbound links)")
    if result.orphans:
        for orphan in result.orphans:
            lines.append(f"  - {_rel(orphan, root)}")
    else:
        lines.append("  None")
    lines.append("")

    # Missing Backlinks section (skip for targeted check)
    if not targeted and result.missing_backlinks:
        lines.append("## Missing Backlinks")
        lines.append("  (A links to B, but B does not link back to A)")
        for src, dst in result.missing_backlinks:
            lines.append(f"  {_rel(src, root)} -> {_rel(dst, root)}")
        lines.append("")

    # Connected Clusters section (skip singletons and targeted check)
    if not targeted and result.clusters:
        lines.append("## Connected Clusters")
        lines.append("  (Groups of documents connected by links)")
        for i, cluster in enumerate(result.clusters, 1):
            lines.append(f"  Cluster {i} ({len(cluster)} files):")
            for member in cluster:
                lines.append(f"    - {_rel(member, root)}")
        lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append(f"  Total files: {len(result.nodes)}")
    lines.append(f"  Total links: {len(result.edges)}")
    lines.append(f"  Broken links: {len(result.broken_links)}")
    lines.append(f"  Orphans: {len(result.orphans)}")
    if not targeted:
        lines.append(f"  Missing backlinks: {len(result.missing_backlinks)}")
        lines.append(f"  Clusters: {len(result.clusters)}")

    return "\n".join(lines)


def _rel(path: Path, root: Path) -> str:
    """Get path relative to root as forward-slash string."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


__all__ = ["format_report"]
