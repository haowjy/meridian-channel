"""Fork materialization pipeline stage."""

from meridian.lib.core.types import HarnessId
from meridian.lib.harness.adapter import SpawnParams, SubprocessHarness


def materialize_fork(
    *,
    adapter: SubprocessHarness,
    run_params: SpawnParams,
    dry_run: bool = False,
) -> SpawnParams:
    """Materialize a fork if conditions are met, returning updated params."""

    should_fork = (
        run_params.continue_fork
        and not dry_run
        and adapter.id == HarnessId.CODEX
        and bool((run_params.continue_harness_session_id or "").strip())
    )
    if not should_fork:
        return run_params

    source_session_id = run_params.continue_harness_session_id or ""
    forked_session_id = adapter.fork_session(source_session_id).strip()
    if not forked_session_id:
        raise RuntimeError("Harness adapter returned empty fork session ID.")

    return run_params.model_copy(
        update={
            "continue_harness_session_id": forked_session_id,
            "continue_fork": False,
        }
    )


__all__ = ["materialize_fork"]
