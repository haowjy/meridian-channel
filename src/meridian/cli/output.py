"""CLI output formatting utilities."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any, Literal, cast

from meridian.lib.serialization import to_jsonable

OutputFormat = Literal["rich", "plain", "json", "porcelain"]
type JSONScalar = str | int | float | bool | None
type JSONValue = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]


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
    """Resolve final output format from flags and TTY state."""

    if json_mode:
        return "json"
    if porcelain_mode:
        return "porcelain"

    if requested is None or requested == "":
        return "rich" if stdout_is_tty else "plain"

    normalized = requested.strip().lower()
    if normalized == "text":
        return "plain"
    if normalized in {"rich", "plain", "json", "porcelain"}:
        if normalized == "rich" and not stdout_is_tty:
            return "plain"
        return cast("OutputFormat", normalized)
    raise SystemExit("--format must be one of: rich, plain, json, porcelain, text")


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


def _emit_plain(value: Any) -> None:
    payload = _to_json_value(value)
    if isinstance(payload, str):
        print(payload)
        return
    print(json.dumps(payload, sort_keys=True, indent=2))


def _emit_rich(value: Any) -> None:
    try:
        from rich.console import Console
    except ImportError:
        _emit_plain(value)
        return

    try:
        console = Console(file=sys.stdout)
        console.print_json(data=_to_json_value(value))
    except Exception:
        _emit_plain(value)


def emit(value: Any, config: OutputConfig) -> None:
    """Emit one payload according to the configured output mode."""

    if config.format == "json":
        print(json.dumps(_to_json_value(value), sort_keys=True))
        return
    if config.format == "porcelain":
        _emit_porcelain(value)
        return
    if config.format == "rich":
        _emit_rich(value)
        return
    _emit_plain(value)
