"""Input/schema helpers shared by MCP and DirectAdapter surfaces."""

from __future__ import annotations

import inspect
import types
from collections.abc import Mapping
from dataclasses import MISSING, fields, is_dataclass
from typing import Any, TypeVar, Union, cast, get_args, get_origin, get_type_hints

PayloadT = TypeVar("PayloadT")


def normalize_optional(annotation: Any) -> tuple[Any, bool]:
    """Return the wrapped type + whether the annotation is Optional[T]."""

    origin = get_origin(annotation)
    if origin is None:
        return annotation, False
    args = get_args(annotation)
    if origin is types.UnionType or origin is Union:
        non_none_args = [arg for arg in args if arg is not type(None)]
        if len(non_none_args) == 1 and len(non_none_args) != len(args):
            return non_none_args[0], True
    return annotation, False


def schema_from_annotation(annotation: Any) -> dict[str, object]:
    normalized, optional = normalize_optional(annotation)
    origin = get_origin(normalized)
    args = get_args(normalized)

    schema: dict[str, object]
    if normalized is str:
        schema = {"type": "string"}
    elif normalized is int:
        schema = {"type": "integer"}
    elif normalized is float:
        schema = {"type": "number"}
    elif normalized is bool:
        schema = {"type": "boolean"}
    elif origin in {list, tuple} and args:
        schema = {"type": "array", "items": schema_from_annotation(args[0])}
    elif isinstance(normalized, type) and is_dataclass(normalized):
        schema = schema_from_type(normalized)
    else:
        schema = {"type": "string"}

    if optional:
        return {"anyOf": [schema, {"type": "null"}]}
    return schema


def schema_from_type(payload_type: type[Any]) -> dict[str, object]:
    """Build a basic JSON schema from dataclass fields."""

    if not is_dataclass(payload_type):
        return {"type": "object", "properties": {}, "additionalProperties": False}

    properties: dict[str, object] = {}
    required: list[str] = []
    for field in fields(payload_type):
        properties[field.name] = schema_from_annotation(field.type)
        if field.default is MISSING and field.default_factory is MISSING:
            required.append(field.name)

    schema: dict[str, object] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


def coerce_scalar(annotation: Any, value: object) -> object:
    """Best-effort scalar coercion for tool inputs."""

    normalized, _ = normalize_optional(annotation)
    if value is None:
        return None
    if normalized is str:
        return str(value)
    if normalized is int:
        return int(cast("Any", value))
    if normalized is float:
        return float(cast("Any", value))
    if normalized is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)
    return value


def coerce_input_payload(payload_type: type[PayloadT], raw_input: object) -> PayloadT:
    """Coerce untyped input dictionaries into typed dataclass payloads."""

    if not is_dataclass(payload_type):
        return payload_type()

    if raw_input is None:
        data: dict[str, object] = {}
    elif isinstance(raw_input, Mapping):
        data = {
            str(key): item for key, item in cast("Mapping[object, object]", raw_input).items()
        }
    else:
        raise TypeError(f"Tool input must be an object, got {type(raw_input).__name__}")

    kwargs: dict[str, object] = {}
    for field in fields(payload_type):
        if field.name in data:
            value = data[field.name]
            origin = get_origin(field.type)
            args = get_args(field.type)
            if origin in {list, tuple} and args and isinstance(value, list):
                items = cast("list[object]", value)
                kwargs[field.name] = [coerce_scalar(args[0], item) for item in items]
            else:
                kwargs[field.name] = coerce_scalar(field.type, value)
            continue

        if field.default is not MISSING:
            kwargs[field.name] = field.default
            continue
        if field.default_factory is not MISSING:
            kwargs[field.name] = field.default_factory()
            continue
        raise TypeError(f"Missing required field '{field.name}'")

    return cast("PayloadT", payload_type(**kwargs))


def signature_from_dataclass(payload_type: type[object]) -> inspect.Signature:
    """Build a callable signature matching dataclass fields for FastMCP schemas."""

    if not is_dataclass(payload_type):
        return inspect.Signature(parameters=[])

    resolved_hints = get_type_hints(payload_type, include_extras=True)
    parameters: list[inspect.Parameter] = []
    for field in fields(payload_type):
        default: object = inspect.Parameter.empty
        if field.default is not MISSING:
            default = field.default
        elif field.default_factory is not MISSING:
            # Dataclass field default factories become optional in tool schemas.
            default = field.default_factory()

        parameters.append(
            inspect.Parameter(
                name=field.name,
                kind=inspect.Parameter.KEYWORD_ONLY,
                default=default,
                annotation=resolved_hints.get(field.name, field.type),
            )
        )

    return inspect.Signature(parameters=parameters)
