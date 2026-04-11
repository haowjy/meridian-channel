from meridian.lib.core.spawn_lifecycle import (
    has_durable_report_completion,
    resolve_execution_terminal_state,
)


def test_has_durable_report_completion_rejects_cancelled_control_frame() -> None:
    assert (
        has_durable_report_completion(
            '{"event_type":"cancelled","payload":{"status":"cancelled","error":"cancelled"}}'
        )
        is False
    )


def test_resolve_execution_terminal_state_returns_cancelled_for_cancel_intent() -> None:
    status, exit_code, error = resolve_execution_terminal_state(
        exit_code=143,
        failure_reason="terminated",
        cancelled=True,
    )
    assert status == "cancelled"
    assert exit_code == 143
    assert error == "terminated"


def test_resolve_execution_terminal_state_prefers_durable_completion_over_cancel() -> None:
    status, exit_code, error = resolve_execution_terminal_state(
        exit_code=143,
        failure_reason="terminated",
        cancelled=True,
        durable_report_completion=True,
        terminated_after_completion=True,
    )
    assert status == "succeeded"
    assert exit_code == 0
    assert error is None
