"""Command assembly helpers for primary launches."""

from __future__ import annotations

from meridian.lib.core.types import ModelId
from meridian.lib.harness.adapter import SpawnParams, SubprocessHarness
from meridian.lib.launch.launch_types import PermissionResolver, ResolvedLaunchSpec

from .run_inputs import (
    ResolvedRunInputs,
    coerce_resolved_run_inputs,
    to_spawn_params,
)


def normalize_system_prompt_passthrough_args(
    passthrough_args: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Extract system-prompt passthroughs and return args without prompt duplicates."""

    cleaned: list[str] = []
    prompt_fragments: list[str] = []
    index = 0
    while index < len(passthrough_args):
        token = passthrough_args[index]

        if token in {"--append-system-prompt", "--system-prompt"}:
            if index + 1 >= len(passthrough_args):
                raise ValueError(f"{token} requires a value")
            prompt_fragments.append(passthrough_args[index + 1])
            index += 2
            continue

        if token.startswith("--append-system-prompt="):
            prompt_fragments.append(token.partition("=")[2])
            index += 1
            continue

        if token.startswith("--system-prompt="):
            prompt_fragments.append(token.partition("=")[2])
            index += 1
            continue

        cleaned.append(token)
        index += 1

    return tuple(cleaned), tuple(prompt_fragments)


def resolve_launch_spec_stage(
    *,
    adapter: SubprocessHarness,
    run_inputs: ResolvedRunInputs | SpawnParams,
    perms: PermissionResolver,
) -> ResolvedLaunchSpec:
    """Stage-owned adapter callsite for `resolve_launch_spec`."""

    return adapter.resolve_launch_spec(to_spawn_params(run_inputs), perms)


def _projected_spec_to_run_inputs(
    *,
    run_inputs: ResolvedRunInputs,
    projected_spec: ResolvedLaunchSpec,
) -> ResolvedRunInputs:
    projected_model = projected_spec.model.strip() if projected_spec.model else ""
    return run_inputs.model_copy(
        update={
            "prompt": projected_spec.prompt,
            "model": ModelId(projected_model) if projected_model else None,
            "effort": projected_spec.effort,
            "extra_args": projected_spec.extra_args,
            "continue_harness_session_id": projected_spec.continue_session_id,
            "continue_fork": projected_spec.continue_fork,
            "interactive": projected_spec.interactive,
            "mcp_tools": projected_spec.mcp_tools,
        }
    )


def build_launch_argv(
    *,
    adapter: SubprocessHarness,
    run_inputs: ResolvedRunInputs | SpawnParams,
    perms: PermissionResolver,
    projected_spec: ResolvedLaunchSpec,
) -> tuple[str, ...]:
    """Stage-owned adapter callsite for `build_command` from projected spec."""

    normalized_inputs = coerce_resolved_run_inputs(run_inputs)
    argv_inputs = _projected_spec_to_run_inputs(
        run_inputs=normalized_inputs,
        projected_spec=projected_spec,
    )
    return tuple(adapter.build_command(to_spawn_params(argv_inputs), perms))


__all__ = [
    "build_launch_argv",
    "normalize_system_prompt_passthrough_args",
    "resolve_launch_spec_stage",
]
