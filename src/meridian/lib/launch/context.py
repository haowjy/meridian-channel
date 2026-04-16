"""Shared launch-context assembly used by subprocess and streaming runners."""

from __future__ import annotations

import os
import shlex
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING

from meridian.lib.core.types import HarnessId, ModelId
from meridian.lib.harness.adapter import SubprocessHarness
from meridian.lib.launch.launch_types import (
    CompositionWarning,
    PermissionResolver,
    PreflightResult,
    ResolvedLaunchSpec,
)
from meridian.lib.state.paths import (
    ProjectPaths,
    resolve_spawn_log_dir,
    resolve_work_scratch_dir,
)

from .command import (
    apply_workspace_projection,
    build_launch_argv,
    resolve_launch_spec_stage,
)
from .cwd import resolve_child_execution_cwd
from .env import build_env_plan, inherit_child_env
from .env import merge_env_overrides as _merge_env_overrides
from .permissions import resolve_permission_pipeline
from .request import LaunchRuntime, SpawnRequest
from .run_inputs import ResolvedRunInputs, build_resolved_run_inputs

if TYPE_CHECKING:
    from meridian.lib.harness.registry import HarnessRegistry

_ALLOWED_MERIDIAN_KEYS: frozenset[str] = frozenset(
    {
        "MERIDIAN_REPO_ROOT",
        "MERIDIAN_STATE_ROOT",
        "MERIDIAN_DEPTH",
        "MERIDIAN_CHAT_ID",
        "MERIDIAN_FS_DIR",
        "MERIDIAN_WORK_ID",
        "MERIDIAN_WORK_DIR",
    }
)


@dataclass(frozen=True)
class RuntimeContext:
    """Sole producer for child `MERIDIAN_*` environment overrides."""

    repo_root: Path
    state_root: Path
    parent_chat_id: str | None
    parent_depth: int
    fs_dir: Path | None
    work_id: str | None
    work_dir: Path | None

    @classmethod
    def from_environment(
        cls,
        *,
        project_paths: ProjectPaths,
        state_root: Path,
    ) -> RuntimeContext:
        parent_chat_id = os.getenv("MERIDIAN_CHAT_ID", "").strip() or None
        parent_depth_raw = os.getenv("MERIDIAN_DEPTH", "0").strip()
        parent_depth = 0
        try:
            parent_depth = max(0, int(parent_depth_raw))
        except (TypeError, ValueError):
            parent_depth = 0

        fs_dir_raw = os.getenv("MERIDIAN_FS_DIR", "").strip()
        work_id_raw = os.getenv("MERIDIAN_WORK_ID", "").strip()
        work_dir_raw = os.getenv("MERIDIAN_WORK_DIR", "").strip()

        return cls(
            # Keep launch semantics unchanged: runtime repo_root follows the
            # execution cwd used by the child process.
            repo_root=project_paths.execution_cwd.resolve(),
            state_root=state_root.resolve(),
            parent_chat_id=parent_chat_id,
            parent_depth=parent_depth,
            fs_dir=Path(fs_dir_raw) if fs_dir_raw else None,
            work_id=work_id_raw or None,
            work_dir=Path(work_dir_raw) if work_dir_raw else None,
        )

    def with_work_id(self, work_id: str | None) -> RuntimeContext:
        normalized = (work_id or "").strip()
        if not normalized:
            return self
        return RuntimeContext(
            repo_root=self.repo_root,
            state_root=self.state_root,
            parent_chat_id=self.parent_chat_id,
            parent_depth=self.parent_depth,
            fs_dir=self.fs_dir,
            work_id=normalized,
            work_dir=resolve_work_scratch_dir(self.state_root, normalized),
        )

    def child_context(self) -> dict[str, str]:
        overrides: dict[str, str] = {
            "MERIDIAN_REPO_ROOT": self.repo_root.as_posix(),
            "MERIDIAN_STATE_ROOT": self.state_root.as_posix(),
            "MERIDIAN_DEPTH": str(self.parent_depth + 1),
        }
        if self.parent_chat_id:
            overrides["MERIDIAN_CHAT_ID"] = self.parent_chat_id
        if self.fs_dir is not None:
            overrides["MERIDIAN_FS_DIR"] = self.fs_dir.as_posix()
        if self.work_id:
            overrides["MERIDIAN_WORK_ID"] = self.work_id
        if self.work_dir is not None:
            overrides["MERIDIAN_WORK_DIR"] = self.work_dir.as_posix()
        elif self.work_id:
            overrides["MERIDIAN_WORK_DIR"] = resolve_work_scratch_dir(
                self.state_root,
                self.work_id,
            ).as_posix()

        if not set(overrides).issubset(_ALLOWED_MERIDIAN_KEYS):
            missing = sorted(set(overrides) - _ALLOWED_MERIDIAN_KEYS)
            raise RuntimeError(f"RuntimeContext.child_context drifted keys: {missing}")
        return overrides


@dataclass(frozen=True)
class LaunchContext:
    argv: tuple[str, ...]
    run_params: ResolvedRunInputs
    perms: PermissionResolver
    spec: ResolvedLaunchSpec
    child_cwd: Path
    env: Mapping[str, str]
    env_overrides: Mapping[str, str]
    report_output_path: Path
    harness: SubprocessHarness
    is_bypass: bool = False
    # I-13: adapter input transformations surface here instead of silently mutating.
    warnings: tuple[CompositionWarning, ...] = ()


def merge_env_overrides(
    *,
    plan_overrides: Mapping[str, str],
    runtime_overrides: Mapping[str, str],
    preflight_overrides: Mapping[str, str],
) -> dict[str, str]:
    """Merge launch env overrides with `MERIDIAN_*` leak checks."""

    return _merge_env_overrides(
        plan_overrides=plan_overrides,
        runtime_overrides=runtime_overrides,
        preflight_overrides=preflight_overrides,
    )


def _resolve_harness_id(
    *,
    request: SpawnRequest,
    runtime: LaunchRuntime,
) -> HarnessId:
    explicit_harness = (request.harness or "").strip()
    if explicit_harness:
        try:
            return HarnessId(explicit_harness)
        except ValueError as exc:
            raise ValueError(f"Unknown harness '{explicit_harness}'.") from exc

    override = (runtime.harness_command_override or "").strip()
    if override:
        command_tokens = shlex.split(override)
        if command_tokens:
            command_name = Path(command_tokens[0]).name.strip().lower()
            if command_name:
                try:
                    return HarnessId(command_name)
                except ValueError as exc:
                    raise ValueError(
                        "LaunchRuntime.harness_command_override must start with a known harness "
                        f"binary name; got '{command_name}'."
                    ) from exc

    raise ValueError("SpawnRequest.harness is required when no command override is present.")


def _resolve_report_output_path(
    *,
    runtime: LaunchRuntime,
    project_paths: ProjectPaths,
    spawn_id: str,
) -> Path:
    report_path_raw = (runtime.report_output_path or "").strip()
    if report_path_raw:
        return Path(report_path_raw).expanduser()
    return resolve_spawn_log_dir(project_paths.repo_root, spawn_id) / "report.md"


def _build_bypass_context(
    *,
    override: str,
    preflight: PreflightResult,
    env_overrides: Mapping[str, str],
) -> tuple[tuple[str, ...], dict[str, str]]:
    command = tuple(
        [*shlex.split(override), *preflight.expanded_passthrough_args]
    )
    if not command:
        raise ValueError("MERIDIAN_HARNESS_COMMAND resolved to an empty command.")
    env = inherit_child_env(
        base_env=os.environ,
        env_overrides=env_overrides,
    )
    return command, env


def build_launch_context(
    *,
    spawn_id: str,
    request: SpawnRequest,
    runtime: LaunchRuntime,
    harness_registry: HarnessRegistry,
    dry_run: bool = False,
    plan_overrides: Mapping[str, str] | None = None,
    runtime_work_id: str | None = None,
) -> LaunchContext:
    """Build deterministic launch context from raw request/runtime inputs."""

    _ = dry_run
    project_paths = ProjectPaths(
        repo_root=Path(runtime.project_paths_repo_root).expanduser().resolve(),
        execution_cwd=Path(runtime.project_paths_execution_cwd).expanduser().resolve(),
    )
    state_root = Path(runtime.state_root).expanduser().resolve()
    harness_id = _resolve_harness_id(request=request, runtime=runtime)
    harness = harness_registry.get_subprocess_harness(harness_id)

    report_output_path = _resolve_report_output_path(
        runtime=runtime,
        project_paths=project_paths,
        spawn_id=spawn_id,
    )
    execution_cwd = project_paths.execution_cwd
    child_cwd = resolve_child_execution_cwd(
        repo_root=execution_cwd,
        spawn_id=spawn_id,
        harness_id=harness.id.value,
    )
    if child_cwd != execution_cwd:
        child_cwd.mkdir(parents=True, exist_ok=True)

    try:
        preflight = harness.preflight(
            execution_cwd=execution_cwd,
            child_cwd=child_cwd,
            passthrough_args=tuple(request.extra_args),
        )
    except AttributeError:
        preflight = PreflightResult.build(
            expanded_passthrough_args=tuple(request.extra_args)
        )

    resolved_agent_metadata = request.agent_metadata
    model = (request.model or "").strip()
    requested_harness_session_id = (
        (request.session.requested_harness_session_id or "").strip() or None
    )
    appended_system_prompt = (
        (resolved_agent_metadata.get("appended_system_prompt") or "").strip() or None
    )
    run_params = build_resolved_run_inputs(
        prompt=request.prompt,
        model=ModelId(model) if model else None,
        effort=request.effort,
        skills=request.skills,
        agent=request.agent,
        adhoc_agent_payload=(resolved_agent_metadata.get("adhoc_agent_payload") or "").strip(),
        extra_args=preflight.expanded_passthrough_args,
        repo_root=child_cwd.as_posix(),
        mcp_tools=request.mcp_tools,
        continue_harness_session_id=requested_harness_session_id,
        continue_fork=request.session.continue_fork,
        report_output_path=report_output_path.as_posix(),
        appended_system_prompt=appended_system_prompt,
        context_from_payload=request.context_from,
    )

    permission_config, perms = resolve_permission_pipeline(
        sandbox=request.sandbox,
        allowed_tools=request.allowed_tools,
        disallowed_tools=request.disallowed_tools,
        approval=request.approval or "default",
        unsafe_no_permissions=runtime.unsafe_no_permissions,
    )
    spec = resolve_launch_spec_stage(adapter=harness, run_inputs=run_params, perms=perms)
    spec = apply_workspace_projection(adapter=harness, spec=spec)
    override = (runtime.harness_command_override or "").strip()
    argv: tuple[str, ...] = ()
    if not override:
        try:
            argv = build_launch_argv(
                adapter=harness,
                run_inputs=run_params,
                perms=perms,
                projected_spec=spec,
            )
        except Exception:
            launch_mode = runtime.launch_mode.strip().lower()
            # Streaming executors launch from typed specs, not subprocess argv.
            if launch_mode not in {"foreground", "background"}:
                raise

    runtime_ctx = RuntimeContext.from_environment(
        project_paths=project_paths,
        state_root=state_root,
    ).with_work_id(runtime_work_id or request.work_id_hint)
    merged_overrides = merge_env_overrides(
        plan_overrides=plan_overrides or {},
        runtime_overrides=runtime_ctx.child_context(),
        preflight_overrides=preflight.extra_env,
    )
    is_bypass = bool(override)
    if is_bypass:
        argv, env = _build_bypass_context(
            override=override,
            preflight=preflight,
            env_overrides=merged_overrides,
        )
    else:
        env = build_env_plan(
            base_env=os.environ,
            adapter=harness,
            run_inputs=run_params,
            permission_config=permission_config,
            runtime_env_overrides=merged_overrides,
        )

    return LaunchContext(
        argv=argv,
        run_params=run_params,
        perms=perms,
        spec=spec,
        child_cwd=child_cwd,
        env=MappingProxyType(env),
        env_overrides=MappingProxyType(merged_overrides),
        report_output_path=report_output_path,
        harness=harness,
        is_bypass=is_bypass,
    )


__all__ = [
    "LaunchContext",
    "RuntimeContext",
    "build_launch_context",
    "merge_env_overrides",
]
