"""Filesystem fixture helpers shared across tests."""

from __future__ import annotations

from pathlib import Path


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_skill(
    repo_root: Path,
    name: str,
    body: str | None = None,
    *,
    description: str | None = None,
) -> Path:
    """Write one skill manifest/body under `.agents/skills/<name>/SKILL.md`."""

    skill_body = body if body is not None else f"# {name}\n"
    summary = description if description is not None else f"{name} skill"
    return _write(
        repo_root / ".agents" / "skills" / name / "SKILL.md",
        (
            "---\n"
            f"name: {name}\n"
            f"description: {summary}\n"
            "---\n\n"
            f"{skill_body}\n"
        ),
    )


def write_agent(
    repo_root: Path,
    *,
    name: str,
    model: str,
    skills: list[str] | tuple[str, ...] = (),
    sandbox: str | None = None,
    mcp_tools: list[str] | tuple[str, ...] | None = None,
    allowed_tools: list[str] | tuple[str, ...] | None = None,
    body: str | None = None,
) -> Path:
    """Write one agent profile under `.agents/agents/<name>.md`."""

    lines = [
        "---",
        f"name: {name}",
        f"model: {model}",
        f"skills: [{', '.join(skills)}]",
    ]
    if sandbox is not None:
        lines.append(f"sandbox: {sandbox}")
    if mcp_tools is not None:
        lines.append(f"mcp-tools: [{', '.join(mcp_tools)}]")
    if allowed_tools is not None:
        lines.append(f"allowed-tools: [{', '.join(allowed_tools)}]")
    lines.append("---")
    lines.extend(["", body if body is not None else f"# {name}"])
    return _write(repo_root / ".agents" / "agents" / f"{name}.md", "\n".join(lines) + "\n")
