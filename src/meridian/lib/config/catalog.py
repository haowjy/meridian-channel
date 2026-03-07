"""Backward-compatible alias catalog exports.

Implementation now lives in `meridian.lib.config.aliases`.
"""

from meridian.lib.config.aliases import (  # noqa: F401
    AliasEntry,
    CatalogModel,
    load_builtin_aliases,
    load_merged_aliases,
    load_model_catalog,
    load_user_aliases,
    resolve_alias,
    resolve_model,
)

__all__ = [
    "AliasEntry",
    "CatalogModel",
    "load_builtin_aliases",
    "load_merged_aliases",
    "load_model_catalog",
    "load_user_aliases",
    "resolve_alias",
    "resolve_model",
]
