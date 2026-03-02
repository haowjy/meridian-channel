"""Shared operation helpers."""

from __future__ import annotations


def merge_warnings(*warnings: str | None) -> str | None:
    """Join non-empty warning strings with consistent separators."""

    parts = [item.strip() for item in warnings if item and item.strip()]
    if not parts:
        return None
    return "; ".join(parts)
