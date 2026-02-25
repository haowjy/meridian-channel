"""Operation registry exports with lazy loading to avoid import cycles."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from meridian.lib.ops.registry import OperationSpec


def get_all_operations() -> list[Any]:
    from meridian.lib.ops.registry import get_all_operations as _get_all_operations

    return _get_all_operations()


def get_operation(name: str) -> Any:
    from meridian.lib.ops.registry import get_operation as _get_operation

    return _get_operation(name)


def operation(spec: Any) -> Any:
    from meridian.lib.ops.registry import operation as _operation

    return _operation(spec)


def __getattr__(name: str) -> Any:
    if name == "OperationSpec":
        from meridian.lib.ops.registry import OperationSpec as _OperationSpec

        return _OperationSpec
    raise AttributeError(name)


__all__ = ["OperationSpec", "get_all_operations", "get_operation", "operation"]
