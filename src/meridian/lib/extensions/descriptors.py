"""Startup-cheap extension descriptor identities.

This module intentionally avoids importing CLI startup catalogs, Pydantic schemas,
or command handlers. Later startup phases can use these identities to connect a
CLI command descriptor to lazily materialized extension metadata.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExtensionDescriptor:
    """Lightweight reference to lazily materialized extension command metadata."""

    fqid: str
    lazy_target: str


__all__ = ["ExtensionDescriptor"]
