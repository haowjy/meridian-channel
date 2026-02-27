"""Registry bootstrap regression coverage."""

from __future__ import annotations

from meridian.lib.ops.registry import get_all_operations


def test_get_all_operations_bootstraps_registry() -> None:
    operations = get_all_operations()
    assert operations, "Expected operation registry to bootstrap and register operations"
