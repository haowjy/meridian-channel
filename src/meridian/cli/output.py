"""CLI output formatting utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal, cast

from meridian.lib.formatting import FormatContext, TextFormattable
from meridian.lib.serialization import to_jsonable

# Re-export so existing `from meridian.cli.output import FormatContext` still works.
__all__ = ["FormatContext", "TextFormattable"]

OutputFormat = Literal["text", "json", "porcelain"]
type JSONScalar = str | int | float | bool | None
type JSONValue = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]

_DEFAULT_FORMAT_CTX = FormatContext()


@dataclass(frozen=True, slots=True)
class OutputConfig:
    format: OutputFormat


def _to_json_value(value: Any) -> JSONValue:
    return cast("JSONValue", to_jsonable(value))


def normalize_output_format(
    *,
    requested: str | None,
    json_mode: bool,
    porcelain_mode: bool,
    stdout_is_tty: bool,
) -> OutputFormat:
    """Resolve final output format from flags and TTY state.

    Default is always "text" regardless of TTY — callers should not need
    to distinguish terminal vs pipe for basic text output.
    """

    if json_mode:
        return "json"
    if porcelain_mode:
        return "porcelain"

    if requested is None or requested == "":
        return "text"

    normalized = requested.strip().lower()
    if normalized in {"text", "json", "porcelain"}:
        return cast("OutputFormat", normalized)
    raise SystemExit("--format must be one of: text, json, porcelain")


def _porcelain_value(value: JSONValue) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _porcelain_line(payload: dict[str, JSONValue]) -> str:
    return "\t".join(f"{key}={_porcelain_value(payload[key])}" for key in sorted(payload))


def _emit_porcelain(value: Any) -> None:
    payload = _to_json_value(value)
    if isinstance(payload, list):
        for item in cast("list[JSONValue]", payload):
            if isinstance(item, dict):
                print(_porcelain_line(cast("dict[str, JSONValue]", item)))
            else:
                print(item)
        return
    if isinstance(payload, dict):
        print(_porcelain_line(cast("dict[str, JSONValue]", payload)))
        return
    print(payload)


def emit(value: Any, config: OutputConfig) -> None:
    """Emit one payload according to the configured output mode."""

    if config.format == "json":
        print(json.dumps(_to_json_value(value), sort_keys=True))
        return
    if config.format == "porcelain":
        _emit_porcelain(value)
        return
    # "text" mode: prefer format_text() if available, fall back to indented JSON
    # for types that have not yet implemented the protocol.
    if isinstance(value, TextFormattable):
        print(value.format_text(_DEFAULT_FORMAT_CTX))
    else:
        print(json.dumps(_to_json_value(value), sort_keys=True, indent=2))
