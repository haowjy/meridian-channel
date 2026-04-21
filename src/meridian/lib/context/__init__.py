"""Context backend for externalized work and knowledge base paths."""

from meridian.lib.context.migration import auto_migrate_contexts
from meridian.lib.context.resolver import ResolvedContextPaths, resolve_context_paths

__all__ = [
    "ResolvedContextPaths",
    "auto_migrate_contexts",
    "resolve_context_paths",
]
