"""Shared spawn lifecycle decisions.

Durable completion evidence is authoritative. If Meridian later sends a cleanup
signal after a final report already exists, that cleanup must not downgrade the
spawn from succeeded to failed.
"""

from meridian.lib.core.domain import SpawnStatus

ACTIVE_SPAWN_STATUSES: frozenset[str] = frozenset({"queued", "running"})
TERMINAL_SPAWN_STATUSES: frozenset[str] = frozenset({"succeeded", "failed", "cancelled"})

_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "queued": frozenset({"running", "succeeded", "failed", "cancelled"}),
    "running": frozenset({"succeeded", "failed", "cancelled"}),
}


def is_active_spawn_status(status: str) -> bool:
    return status in ACTIVE_SPAWN_STATUSES


def validate_transition(from_status: SpawnStatus, to_status: SpawnStatus) -> None:
    allowed = _ALLOWED_TRANSITIONS.get(from_status, frozenset())
    if to_status not in allowed:
        raise ValueError(f"Illegal spawn transition: {from_status} -> {to_status}")


def has_durable_report_completion(report_text: str | None) -> bool:
    """Return True when a non-empty final report is available on disk."""

    return bool(report_text and report_text.strip())


def resolve_execution_terminal_state(
    *,
    exit_code: int,
    failure_reason: str | None,
    durable_report_completion: bool = False,
    terminated_after_completion: bool = False,
) -> tuple[SpawnStatus, int, str | None]:
    """Normalize one execution outcome into the persisted terminal state."""

    if durable_report_completion and terminated_after_completion:
        return "succeeded", 0, None
    if exit_code == 0:
        return "succeeded", 0, failure_reason
    return "failed", exit_code, failure_reason


def resolve_reconciled_terminal_state(
    *,
    durable_report_completion: bool,
    fallback_error: str,
) -> tuple[SpawnStatus, int, str | None]:
    """Resolve the terminal state produced by read-path reconciliation."""

    if durable_report_completion:
        return "succeeded", 0, None
    return "failed", 1, fallback_error
