"""Ensure all registered operation output types implement TextFormattable.

Prevents silent JSON fallback from shipping for new output types that
forgot to add format_text().
"""

from __future__ import annotations

import dataclasses
import inspect
import types
from typing import Any, get_type_hints

from meridian.lib.formatting import FormatContext
from meridian.lib.ops.registry import get_all_operations


def test_all_output_types_are_text_formattable() -> None:
    """Every registered operation output_type must satisfy TextFormattable."""
    missing: list[str] = []
    for spec in get_all_operations():
        if not hasattr(spec.output_type, "format_text"):
            missing.append(f"{spec.output_type.__name__} (from {spec.name})")
    assert not missing, (
        "The following output types do not implement format_text():\n"
        + "\n".join(f"  - {name}" for name in missing)
    )


def test_format_text_accepts_format_context() -> None:
    """format_text() must accept a FormatContext parameter."""
    for spec in get_all_operations():
        if not hasattr(spec.output_type, "format_text"):
            continue
        sig = inspect.signature(spec.output_type.format_text)
        params = list(sig.parameters.keys())
        assert len(params) >= 2, (
            f"{spec.output_type.__name__}.format_text() must accept a "
            f"FormatContext parameter, but only has params: {params}"
        )


_DUMMY_VALUES: dict[type, Any] = {
    str: "",
    int: 0,
    float: 0.0,
    bool: False,
}


def _resolve_dummy(annotation: Any) -> Any:
    """Pick a dummy value for a type annotation."""
    if annotation in _DUMMY_VALUES:
        return _DUMMY_VALUES[annotation]

    origin = getattr(annotation, "__origin__", None)
    args = getattr(annotation, "__args__", ())

    # Handle X | None union types — use None since the format_text() methods
    # are expected to handle None gracefully for optional fields.
    if origin is types.UnionType:
        if type(None) in args:
            return None
        # Non-None union — try first arg
        return _resolve_dummy(args[0]) if args else ""

    if origin is tuple:
        return ()
    if origin is dict:
        return {}

    return ""


def _make_dummy(output_type: type[Any]) -> Any:
    """Construct a minimal instance of a frozen dataclass using defaults and dummy values."""
    if not dataclasses.is_dataclass(output_type):
        return output_type()

    kwargs: dict[str, Any] = {}
    hints = get_type_hints(output_type)
    for f in dataclasses.fields(output_type):
        if f.default is not dataclasses.MISSING or f.default_factory is not dataclasses.MISSING:
            continue
        kwargs[f.name] = _resolve_dummy(hints.get(f.name))
    return output_type(**kwargs)


def test_format_text_returns_nonempty_string() -> None:
    """Instantiate each output type with minimal data and call format_text().

    Catches runtime errors (missing fields, None dereferences, etc.) that
    structural compliance tests cannot detect.
    """
    failures: list[str] = []
    for spec in get_all_operations():
        if not hasattr(spec.output_type, "format_text"):
            continue
        try:
            instance = _make_dummy(spec.output_type)
            result = instance.format_text(FormatContext())
        except Exception as exc:
            failures.append(f"{spec.output_type.__name__} (from {spec.name}): {exc}")
            continue
        if not isinstance(result, str):
            failures.append(
                f"{spec.output_type.__name__} (from {spec.name}): "
                f"returned {type(result).__name__}, expected str"
            )
    assert not failures, (
        "format_text() failed for the following output types:\n"
        + "\n".join(f"  - {f}" for f in failures)
    )
