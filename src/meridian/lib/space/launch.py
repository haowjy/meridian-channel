"""Primary agent launcher — thin orchestrator.

The heavy lifting lives in:
- _launch_types.py   — shared dataclasses and prompt builder
- _launch_resolve.py — harness routing and session metadata resolution
- _launch_command.py — command assembly and environment building
- _launch_process.py — process lifecycle and lock management
"""

from __future__ import annotations

from pathlib import Path

from meridian.lib.harness.registry import HarnessRegistry

# Re-export public API from submodules so existing imports keep working.
from meridian.lib.space._launch_command import (
    _PrimaryHarnessContext as _PrimaryHarnessContext,
    _build_harness_command as _build_harness_command,
    _build_harness_context as _build_harness_context,
    _build_space_env as _build_space_env,
    _normalize_system_prompt_passthrough_args as _normalize_system_prompt_passthrough_args,
)
from meridian.lib.space._launch_process import (
    _LaunchContext as _LaunchContext,
    _ProcessOutcome as _ProcessOutcome,
    _prepare_launch_context,
    _run_harness_process,
    cleanup_orphaned_locks as cleanup_orphaned_locks,
    space_lock_path as space_lock_path,
)
from meridian.lib.space._launch_resolve import (
    _resolve_harness as _resolve_harness,
    _resolve_primary_session_metadata as _resolve_primary_session_metadata,
)
from meridian.lib.space._launch_types import (
    SpaceLaunchRequest as SpaceLaunchRequest,
    SpaceLaunchResult as SpaceLaunchResult,
    _PrimarySessionMetadata as _PrimarySessionMetadata,
    build_primary_prompt as build_primary_prompt,
)


def launch_primary(
    *,
    repo_root: Path,
    request: SpaceLaunchRequest,
    harness_registry: HarnessRegistry,
) -> SpaceLaunchResult:
    """Launch primary agent process and wait for exit."""

    ctx = _prepare_launch_context(repo_root, request, harness_registry)

    if request.dry_run:
        command = _build_harness_command(
            repo_root=repo_root,
            request=ctx.command_request,
            prompt=ctx.prompt,
            harness_registry=harness_registry,
            chat_id="dry-run",
            config=ctx.config,
        )
        return SpaceLaunchResult(
            command=command,
            exit_code=0,
            lock_path=ctx.lock_path,
            continue_ref=None,
        )

    outcome = _run_harness_process(repo_root, request, ctx, harness_registry)
    continue_ref = outcome.resolved_harness_session_id.strip() or None

    return SpaceLaunchResult(
        command=outcome.command,
        exit_code=outcome.exit_code,
        lock_path=ctx.lock_path,
        continue_ref=continue_ref,
    )
