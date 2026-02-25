"""CLI command handlers for diag.* operations."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any

from meridian.lib.ops.diag import (
    DiagDoctorInput,
    DiagRepairInput,
    diag_doctor_sync,
    diag_repair_sync,
)
from meridian.lib.ops.registry import get_all_operations

Emitter = Callable[[Any], None]


def _diag_doctor(emit: Emitter) -> None:
    emit(diag_doctor_sync(DiagDoctorInput()))


def _diag_repair(emit: Emitter) -> None:
    emit(diag_repair_sync(DiagRepairInput()))


def register_diag_commands(app: Any, emit: Emitter) -> tuple[set[str], dict[str, str]]:
    handlers: dict[str, Callable[[], Callable[..., None]]] = {
        "diag.doctor": lambda: partial(_diag_doctor, emit),
        "diag.repair": lambda: partial(_diag_repair, emit),
    }

    registered: set[str] = set()
    descriptions: dict[str, str] = {}

    for op in get_all_operations():
        if op.cli_group != "diag" or op.mcp_only:
            continue
        handler_factory = handlers.get(op.name)
        if handler_factory is None:
            raise ValueError(f"No CLI handler registered for operation '{op.name}'")
        handler = handler_factory()
        handler.__name__ = f"cmd_{op.cli_group}_{op.cli_name}"
        app.command(handler, name=op.cli_name, help=op.description)
        registered.add(f"{op.cli_group}.{op.cli_name}")
        descriptions[op.name] = op.description

    return registered, descriptions
