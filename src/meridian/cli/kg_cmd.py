"""CLI handlers for `meridian kg` commands.

Registers `kg graph` and `kg check` on the shared `kg_app` via
decorator-at-import. Import this module from ``_register_group_commands``
in ``cli/main.py`` to activate the commands.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

from cyclopts import Parameter

from meridian.cli.app_tree import kg_app


@kg_app.command(name="graph")
def cmd_kg_graph(
    root: Annotated[
        Path,
        Parameter(help="Root directory to analyze (default: cwd)."),
    ] = Path("."),
    no_backlinks: Annotated[
        bool,
        Parameter(name="--no-backlinks", help="Skip missing-backlink analysis."),
    ] = False,
    no_clusters: Annotated[
        bool,
        Parameter(name="--no-clusters", help="Skip connected-cluster analysis."),
    ] = False,
) -> None:
    """Analyze document relationships, broken links, orphans, and clusters."""

    from meridian.lib.kg.graph import build_analysis
    from meridian.lib.kg.report import format_report

    root_resolved = root.resolve()
    if not root_resolved.exists():
        print(f"Error: root not found: {root}", file=sys.stderr)
        raise SystemExit(2)
    if not root_resolved.is_dir():
        print(f"Error: root is not a directory: {root}", file=sys.stderr)
        raise SystemExit(2)

    result = build_analysis(
        root=root_resolved,
        include_backlinks=not no_backlinks,
        include_clusters=not no_clusters,
    )
    print(format_report(result, root=root_resolved))
    raise SystemExit(1 if result.broken_links else 0)


@kg_app.command(name="check")
def cmd_kg_check(
    path: Annotated[
        Path,
        Parameter(help="File or directory to check for broken links."),
    ] = Path("."),
) -> None:
    """Check for broken links. Exit 0 if clean, exit 1 if broken links found."""

    from meridian.lib.kg.graph import build_analysis

    resolved = path.resolve()
    if not resolved.exists():
        print(f"Error: path not found: {path}", file=sys.stderr)
        raise SystemExit(2)
    if not resolved.is_dir():
        resolved = resolved.parent

    result = build_analysis(
        root=resolved,
        include_backlinks=False,
        include_clusters=False,
    )

    if not result.broken_links:
        print(f"No broken links ({len(result.nodes)} files, {len(result.edges)} links)")
        raise SystemExit(0)

    for bl in result.broken_links:
        src_rel = bl.src.relative_to(resolved) if bl.src.is_relative_to(resolved) else bl.src
        print(f"  {src_rel}:{bl.line} -> {bl.dst} [{bl.kind}]")

    print(
        f"\n{len(result.broken_links)} broken links "
        f"({len(result.nodes)} files, {len(result.edges)} links)",
        file=sys.stderr,
    )
    raise SystemExit(1)


__all__ = [
    "cmd_kg_check",
    "cmd_kg_graph",
]
