"""Base skill injection rules."""

from __future__ import annotations

from typing import Literal

BaseSkillMode = Literal["standalone", "supervisor"]

RUN_AGENT_SKILL = "run-agent"
AGENT_SKILL = "agent"
ORCHESTRATE_SKILL = "orchestrate"


def base_skill_names(mode: BaseSkillMode) -> tuple[str, ...]:
    """Return required base skill names for the selected mode."""

    if mode == "standalone":
        return (RUN_AGENT_SKILL, AGENT_SKILL)
    return (RUN_AGENT_SKILL, AGENT_SKILL, ORCHESTRATE_SKILL)


def inject_base_skills(requested: list[str], mode: BaseSkillMode) -> tuple[str, ...]:
    """Merge base skills with requested skills while preserving order."""

    merged: list[str] = list(base_skill_names(mode))
    for skill in requested:
        candidate = skill.strip()
        if candidate and candidate not in merged:
            merged.append(candidate)
    return tuple(merged)

