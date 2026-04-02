"""Shared policy helpers for configured default agents."""

from pathlib import Path

from meridian.lib.catalog.agent import AgentProfile, load_agent_profile


def _expected_agent_profile_path(agent_name: str) -> str:
    return (Path(".agents") / "agents" / f"{agent_name}.md").as_posix()


def _default_agent_missing_warning(
    *,
    configured_profile: str,
    builtin_profile: str,
    config_key: str,
) -> str:
    lines = [
        f"Configured {config_key} '{configured_profile}' is unavailable locally.",
        f"Expected: {_expected_agent_profile_path(configured_profile)}",
    ]
    if builtin_profile and configured_profile != builtin_profile:
        lines.append(
            f"Meridian will use builtin default '{builtin_profile}' when it is available."
        )
    lines.append("Run `meridian mars sync` to populate missing agent profiles.")
    return "\n".join(lines)


def configured_default_agent_warning(
    *,
    repo_root: Path,
    configured_agent: str,
    builtin_default: str,
    config_key: str,
) -> str | None:
    configured_profile = configured_agent.strip()
    if not configured_profile:
        return None

    builtin_profile = builtin_default.strip()

    try:
        load_agent_profile(
            configured_profile,
            repo_root=repo_root,
        )
    except FileNotFoundError:
        return _default_agent_missing_warning(
            configured_profile=configured_profile,
            builtin_profile=builtin_profile,
            config_key=config_key,
        )

    return None


def resolve_agent_profile_with_builtin_fallback(
    *,
    repo_root: Path,
    requested_agent: str | None,
    configured_default: str,
    builtin_default: str,
) -> tuple[AgentProfile | None, str | None]:
    requested_profile = requested_agent.strip() if requested_agent is not None else ""
    if requested_profile:
        return (
            load_agent_profile(
                requested_profile,
                repo_root=repo_root,
            ),
            None,
        )

    configured_profile = configured_default.strip()
    if configured_profile:
        try:
            return (
                load_agent_profile(
                    configured_profile,
                    repo_root=repo_root,
                ),
                None,
            )
        except FileNotFoundError:
            fallback_profile = builtin_default.strip()
            if fallback_profile and fallback_profile != configured_profile:
                return (
                    load_agent_profile(
                        fallback_profile,
                        repo_root=repo_root,
                    ),
                    "Configured default agent "
                    f"'{configured_profile}' is unavailable; using builtin default "
                    f"'{fallback_profile}'.",
                )
            raise

    return None, None
