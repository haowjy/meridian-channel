"""CLI command handler for standalone doctor operation."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING, Any

from meridian.lib.ops.diag import DoctorInput, doctor_sync
from meridian.lib.ops.registry import get_all_operations

if TYPE_CHECKING:
    from cyclopts import App

Emitter = Callable[[Any], None]


def _doctor(emit: Emitter) -> None:
    emit(doctor_sync(DoctorInput()))


def register_doctor_command(app: App, emit: Emitter) -> tuple[set[str], dict[str, str]]:
    registered: set[str] = set()
    descriptions: dict[str, str] = {}

    for op in get_all_operations():
        if op.name != "doctor" or op.mcp_only:
            continue
        handler = partial(_doctor, emit)
        handler.__name__ = "cmd_doctor"
        app.command(handler, name="doctor", help=op.description)
        registered.add(f"{op.cli_group}.{op.cli_name}")
        descriptions[op.name] = op.description

    return registered, descriptions
