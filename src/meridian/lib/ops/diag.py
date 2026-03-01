"""Diagnostics operations for file-authoritative state."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from meridian.lib.config._paths import resolve_path_list
from meridian.lib.ops._runtime import build_runtime
from meridian.lib.ops.registry import OperationSpec, operation
from meridian.lib.space import space_file
from meridian.lib.space.session_store import cleanup_stale_sessions, list_active_sessions
from meridian.lib.state import run_store
from meridian.lib.state.paths import resolve_all_spaces_dir

if TYPE_CHECKING:
    from meridian.lib.formatting import FormatContext


@dataclass(frozen=True, slots=True)
class DiagDoctorInput:
    repo_root: str | None = None


@dataclass(frozen=True, slots=True)
class DiagRepairInput:
    repo_root: str | None = None


@dataclass(frozen=True, slots=True)
class DiagDoctorOutput:
    ok: bool
    repo_root: str
    spaces_checked: int
    runs_checked: int
    agents_dir: str
    skills_dir: str
    warnings: tuple[str, ...] = ()

    def format_text(self, ctx: FormatContext | None = None) -> str:
        """Key-value health check output for text output mode."""
        from meridian.cli.format_helpers import kv_block

        status = "ok" if self.ok else "WARNINGS"
        pairs: list[tuple[str, str | None]] = [
            ("ok", status),
            ("repo_root", self.repo_root),
            ("spaces_checked", str(self.spaces_checked)),
            ("runs_checked", str(self.runs_checked)),
            ("agents_dir", self.agents_dir),
            ("skills_dir", self.skills_dir),
        ]
        result = kv_block(pairs)
        for warning in self.warnings:
            result += f"\nwarning: {warning}"
        return result


@dataclass(frozen=True, slots=True)
class DiagRepairOutput:
    ok: bool
    repaired: tuple[str, ...]

    def format_text(self, ctx: FormatContext | None = None) -> str:
        """Repair summary for text output mode."""
        if not self.repaired:
            return "ok: no repairs needed"
        items = ", ".join(self.repaired)
        return f"ok: repaired {items}"


def _space_dirs(repo_root: Path) -> list[Path]:
    spaces_dir = resolve_all_spaces_dir(repo_root)
    if not spaces_dir.is_dir():
        return []
    return [child for child in sorted(spaces_dir.iterdir()) if child.is_dir()]


def _detect_missing_or_corrupt_spaces(repo_root: Path) -> list[str]:
    bad: list[str] = []
    for space_dir in _space_dirs(repo_root):
        if space_file.get_space(repo_root, space_dir.name) is None:
            bad.append(space_dir.name)
    return bad


def _count_runs(repo_root: Path) -> int:
    total = 0
    for space_dir in _space_dirs(repo_root):
        if space_file.get_space(repo_root, space_dir.name) is None:
            continue
        total += len(run_store.list_runs(space_dir))
    return total


def diag_doctor_sync(payload: DiagDoctorInput) -> DiagDoctorOutput:
    runtime = build_runtime(payload.repo_root)
    search_paths = runtime.config.search_paths
    agents_dirs = resolve_path_list(
        search_paths.agents,
        search_paths.global_agents,
        runtime.repo_root,
    )
    skills_dirs = resolve_path_list(
        search_paths.skills,
        search_paths.global_skills,
        runtime.repo_root,
    )

    warnings: list[str] = []
    if not skills_dirs:
        warnings.append("No configured skills directories were found.")
    if not agents_dirs:
        warnings.append("No configured agent profile directories were found.")

    bad_spaces = _detect_missing_or_corrupt_spaces(runtime.repo_root)
    if bad_spaces:
        warnings.append(
            "Missing/corrupt space.json detected for spaces: " + ", ".join(sorted(bad_spaces))
        )

    for space_dir in _space_dirs(runtime.repo_root):
        record = space_file.get_space(runtime.repo_root, space_dir.name)
        if record is None:
            continue
        active_sessions = list_active_sessions(space_dir)
        if record.status == "active" and not active_sessions:
            warnings.append(f"Space '{record.id}' is marked active with no live sessions.")

        running = [row.id for row in run_store.list_runs(space_dir) if row.status == "running"]
        if running:
            warnings.append(f"Space '{record.id}' has orphan candidate running runs: {', '.join(running)}")

    agents_dir = agents_dirs[0] if agents_dirs else runtime.repo_root
    skills_dir = skills_dirs[0] if skills_dirs else runtime.repo_root

    return DiagDoctorOutput(
        ok=not warnings,
        repo_root=runtime.repo_root.as_posix(),
        spaces_checked=len(_space_dirs(runtime.repo_root)),
        runs_checked=_count_runs(runtime.repo_root),
        agents_dir=agents_dir.as_posix(),
        skills_dir=skills_dir.as_posix(),
        warnings=tuple(warnings),
    )


async def diag_doctor(payload: DiagDoctorInput) -> DiagDoctorOutput:
    return await asyncio.to_thread(diag_doctor_sync, payload)


def _repair_stale_session_locks(repo_root: Path) -> int:
    repaired = 0
    for space_dir in _space_dirs(repo_root):
        if space_file.get_space(repo_root, space_dir.name) is None:
            continue
        repaired += len(cleanup_stale_sessions(space_dir))
    return repaired


def _repair_orphan_runs(repo_root: Path) -> int:
    repaired = 0
    for space_dir in _space_dirs(repo_root):
        record = space_file.get_space(repo_root, space_dir.name)
        if record is None:
            continue

        active_sessions = set(list_active_sessions(space_dir))
        for run in run_store.list_runs(space_dir):
            if run.status != "running":
                continue
            if run.session_id is not None and run.session_id in active_sessions:
                continue

            run_store.finalize_run(
                space_dir,
                run.id,
                status="failed",
                exit_code=1,
                error="orphan_run",
            )
            repaired += 1
    return repaired


def _repair_stale_space_status(repo_root: Path) -> int:
    repaired = 0
    for space_dir in _space_dirs(repo_root):
        record = space_file.get_space(repo_root, space_dir.name)
        if record is None:
            continue

        active_sessions = list_active_sessions(space_dir)
        desired = "active" if active_sessions else "closed"
        if record.status != desired:
            space_file.update_space_status(repo_root, record.id, desired)
            repaired += 1
    return repaired


def diag_repair_sync(payload: DiagRepairInput) -> DiagRepairOutput:
    runtime = build_runtime(payload.repo_root)
    repaired: list[str] = []

    stale_locks = _repair_stale_session_locks(runtime.repo_root)
    if stale_locks > 0:
        repaired.append("stale_session_locks")

    orphan_runs = _repair_orphan_runs(runtime.repo_root)
    if orphan_runs > 0:
        repaired.append("orphan_runs")

    stale_status = _repair_stale_space_status(runtime.repo_root)
    if stale_status > 0:
        repaired.append("stale_space_status")

    bad_spaces = _detect_missing_or_corrupt_spaces(runtime.repo_root)
    if bad_spaces:
        repaired.append("missing_or_corrupt_space_json")

    return DiagRepairOutput(ok=True, repaired=tuple(sorted(set(repaired))))


async def diag_repair(payload: DiagRepairInput) -> DiagRepairOutput:
    return await asyncio.to_thread(diag_repair_sync, payload)


operation(
    OperationSpec[DiagDoctorInput, DiagDoctorOutput](
        name="diag.doctor",
        handler=diag_doctor,
        sync_handler=diag_doctor_sync,
        input_type=DiagDoctorInput,
        output_type=DiagDoctorOutput,
        cli_group="diag",
        cli_name="doctor",
        mcp_name="diag_doctor",
        description="Run diagnostics checks.",
    )
)

operation(
    OperationSpec[DiagRepairInput, DiagRepairOutput](
        name="diag.repair",
        handler=diag_repair,
        sync_handler=diag_repair_sync,
        input_type=DiagRepairInput,
        output_type=DiagRepairOutput,
        cli_group="diag",
        cli_name="repair",
        mcp_name="diag_repair",
        description="Repair common state issues.",
    )
)
