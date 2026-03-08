"""CLI command handler for standalone doctor operation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cyclopts import App
from meridian.lib.ops.diag import DoctorInput, doctor_sync
from meridian.lib.ops.registry import get_all_operations

Emitter = Callable[[Any], None]


def _doctor(emit: Emitter) -> None:
    emit(doctor_sync(DoctorInput()))


def register_doctor_command(app: App, emit: Emitter) -> tuple[set[str], dict[str, str]]:
    registered: set[str] = set()
    descriptions: dict[str, str] = {}

    for op in get_all_operations():
        if op.name != "doctor" or op.mcp_only:
            continue

        def cmd_doctor() -> None:
            _doctor(emit)

        app.command(cmd_doctor, name="doctor", help=op.description)
        registered.add(f"{op.cli_group}.{op.cli_name}")
        descriptions[op.name] = op.description

    return registered, descriptions
