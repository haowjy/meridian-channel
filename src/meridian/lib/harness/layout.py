"""Re-export shim -- contents merged into materialize.py."""

from meridian.lib.harness.materialize import (  # noqa: F401
    HARNESS_NATIVE_DIRS as HARNESS_NATIVE_DIRS,
    HarnessLayout as HarnessLayout,
    harness_layout as harness_layout,
    is_agent_native as is_agent_native,
    is_skill_native as is_skill_native,
    materialization_target_agents as materialization_target_agents,
    materialization_target_skills as materialization_target_skills,
    resolve_native_dir as resolve_native_dir,
)
