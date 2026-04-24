"""Knowledge graph analysis: document graph and link health."""

from meridian.lib.kg.graph import build_analysis
from meridian.lib.kg.report import format_report
from meridian.lib.kg.serializer import serialize_analysis, serialize_check
from meridian.lib.kg.types import (
    AnalysisResult,
    GraphEdge,
    GraphNode,
)

__all__ = [
    "AnalysisResult",
    "GraphEdge",
    "GraphNode",
    "build_analysis",
    "format_report",
    "serialize_analysis",
    "serialize_check",
]
