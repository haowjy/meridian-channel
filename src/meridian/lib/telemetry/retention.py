"""Retention cleanup for local telemetry JSONL segments."""

from __future__ import annotations

import os
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from meridian.lib.telemetry.router import emit_telemetry

_DEFAULT_MAX_AGE_DAYS = 7
_DEFAULT_MAX_TOTAL_BYTES = 100_000_000


@dataclass(frozen=True)
class SegmentOwner:
    """Parsed identity from a segment filename."""

    logical_owner: str
    pid: int

    @property
    def is_cli_or_chat(self) -> bool:
        return self.logical_owner in ("cli", "chat")


@dataclass(frozen=True)
class SegmentInfo:
    path: Path
    owner: SegmentOwner | None
    size: int
    mtime: float
    live: bool

    @property
    def orphaned(self) -> bool:
        return self.owner is None


def parse_segment_owner(path: Path) -> SegmentOwner | None:
    """Parse owner from compound telemetry segment filenames.

    Compound format: <logical_owner>.<pid>-<seq>.jsonl.
    Legacy format <pid>-<seq>.jsonl is returned as None so retention treats it
    as orphaned.
    """
    if path.suffix != ".jsonl":
        return None
    stem = path.stem

    dot_idx = stem.rfind(".")
    if dot_idx > 0:
        logical_owner = stem[:dot_idx]
        instance_and_seq = stem[dot_idx + 1 :]
        parts = instance_and_seq.split("-", 1)
        if len(parts) == 2:
            try:
                pid_text, seq_text = parts
                if not pid_text.isdigit() or not seq_text.isdigit():
                    return None
                pid = int(pid_text)
                int(seq_text)
                return SegmentOwner(logical_owner=logical_owner, pid=pid)
            except ValueError:
                pass

    return None


def parse_segment_pid(path: Path) -> int | None:
    """Deprecated compatibility wrapper for compound segment PID parsing."""
    owner = parse_segment_owner(path)
    return owner.pid if owner is not None else None


def run_retention_cleanup(
    telemetry_dir: Path,
    *,
    runtime_root: Path | None = None,
    max_age_days: int = _DEFAULT_MAX_AGE_DAYS,
    max_total_bytes: int = _DEFAULT_MAX_TOTAL_BYTES,
) -> None:
    """Delete eligible telemetry segments by age and total-size cap."""
    telemetry_dir.mkdir(parents=True, exist_ok=True)
    now = time.time()
    current_pid = os.getpid()
    segments = _list_segments(telemetry_dir, runtime_root=runtime_root)
    max_age_secs = max_age_days * 24 * 60 * 60

    for segment in list(segments):
        if segment.owner is not None and segment.owner.pid == current_pid:
            continue
        if segment.live:
            continue
        if now - segment.mtime > max_age_secs and _delete_segment(segment.path):
            segments.remove(segment)

    total_size = sum(segment.size for segment in segments if segment.path.exists())
    if total_size <= max_total_bytes:
        return

    # Prefer orphaned segments when enforcing the hard cap.
    for segment in sorted((s for s in segments if s.orphaned), key=lambda s: s.mtime):
        if total_size <= max_total_bytes:
            return
        if _delete_segment(segment.path):
            total_size -= segment.size

    # Last resort: closed files not owned by the current or any live process.
    for segment in sorted(
        (
            s
            for s in segments
            if (s.owner is None or s.owner.pid != current_pid)
            and not s.live
            and s.path.exists()
        ),
        key=lambda s: s.mtime,
    ):
        if total_size <= max_total_bytes:
            return
        if _delete_segment(segment.path):
            total_size -= segment.size
            emit_telemetry(
                "runtime",
                "runtime.telemetry.consumer_data_lost",
                scope="telemetry.retention",
                severity="warning",
                data={"segment": segment.path.name, "bytes_lost": segment.size},
            )


def _list_segments(
    telemetry_dir: Path,
    *,
    runtime_root: Path | None = None,
) -> list[SegmentInfo]:
    # Import lazily to avoid telemetry/core lifecycle import cycles at module load time.
    from meridian.lib.state.liveness import is_process_alive, is_spawn_genuinely_active

    current_pid = os.getpid()
    segments: list[SegmentInfo] = []
    for path in telemetry_dir.glob("*.jsonl"):
        owner = parse_segment_owner(path)
        with suppress(OSError):
            stat = path.stat()
            live = False
            if owner is not None:
                if owner.pid == current_pid:
                    live = True
                elif owner.is_cli_or_chat:
                    live = is_process_alive(owner.pid)
                elif runtime_root is not None:
                    live = is_spawn_genuinely_active(runtime_root, owner.logical_owner)
                else:
                    live = is_process_alive(owner.pid)
            segments.append(
                SegmentInfo(
                    path=path,
                    owner=owner,
                    size=stat.st_size,
                    mtime=stat.st_mtime,
                    live=live,
                )
            )
    return segments


def _delete_segment(path: Path) -> bool:
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False
