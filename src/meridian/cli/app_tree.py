"""CLI app tree objects shared by the main router."""

from cyclopts import App

from meridian import __version__

# Curated help for agent mode: only commands useful for subagent callers.
# Not auto-generated — update when adding agent-facing commands.
AGENT_ROOT_HELP = """Usage: meridian COMMAND [ARGS]

Multi-agent orchestration across Claude, Codex, and OpenCode.

Quick start:
  meridian spawn -m MODEL -p "prompt"   Create a subagent run
  meridian spawn wait ID                Wait for results
  meridian models list                  See available models

Run 'meridian spawn -h' for full usage.

Commands:
  init     Initialize repo config; optional --link wiring for tool directories
  mars     Forward arguments to bundled mars CLI
  spawn    Create and manage subagent runs (includes report subgroup)
  session  Read and search harness session transcripts
  work     Work item dashboard and coordination
  models   Model catalog
  config   Repository config inspection and overrides
  workspace  Local workspace topology setup
  doctor   Health check and orphan reconciliation

Output:
  Agent mode defaults to JSON. All commands emit structured JSON.
  Use --format text to force human-readable output.
"""

app = App(
    name="meridian",
    help=(
        "Multi-agent orchestration across Claude, Codex, and OpenCode.\n\n"
        "Global harness selection: --harness (or prefix with claude/codex/opencode)\n"
        "Bundled package manager: meridian mars <args>\n\n"
        'Run "meridian spawn -h" for subagent usage.'
    ),
    version=__version__,
    help_formatter="plain",
)
spawn_app = App(
    name="spawn",
    help=(
        "Run subagents with a model and prompt.\n"
        "Runs in foreground by default; returns when the spawn reaches a terminal state. "
        "Use --background to return immediately with the spawn ID."
    ),
    help_epilogue=(
        "Examples:\n\n"
        '  meridian spawn -m gpt-5.3-codex -p "Fix the bug in auth.py"\n\n'
        '  meridian spawn -m claude-sonnet-4-6 -p "Review" -f src/main.py\n\n'
        "  meridian spawn wait SPAWN_ID\n"
    ),
    help_formatter="plain",
)
report_app = App(
    name="report",
    help="Report management commands.",
    help_epilogue=(
        "Examples:\n\n"
        "  meridian spawn report show p107\n\n"
        '  meridian spawn report search "auth bug"\n'
    ),
    help_formatter="plain",
)
session_app = App(
    name="session",
    help=(
        "Inspect harness session transcripts.\n\n"
        "Session refs accept three forms: chat ids (c123), spawn ids (p123),\n"
        "or raw harness session ids. By default, commands operate on\n"
        "$MERIDIAN_CHAT_ID -- inherited from the spawning session -- so a\n"
        "subagent reads its parent's transcript, not its own."
    ),
    help_formatter="plain",
)
work_app = App(
    name="work",
    help=(
        "Active activity grouped by work, plus work item coordination commands. "
        "Unassigned spawns appear under '(no work)'."
    ),
    help_formatter="plain",
)
models_app = App(name="models", help="Model catalog commands", help_formatter="plain")
streaming_app = App(name="streaming", help="Streaming layer commands", help_formatter="plain")
config_app = App(
    name="config",
    help=(
        "Repository-level config (meridian.toml) for default\n"
        "agent, model, harness, timeouts, and output verbosity.\n\n"
        "Resolved values are evaluated independently per field -- a CLI\n"
        "override on one field does not pull other fields from the same\n"
        "source. Use `meridian config show` to see each value with its\n"
        "source annotation."
    ),
    help_formatter="plain",
)
workspace_app = App(
    name="workspace",
    help=(
        "Local workspace topology commands.\n\n"
        "Workspace topology is stored in workspace.local.toml next to the active .meridian/ "
        "directory and is intentionally local-only."
    ),
    help_formatter="plain",
)
completion_app = App(name="completion", help="Shell completion helpers", help_formatter="plain")

app.command(spawn_app, name="spawn")
spawn_app.command(report_app, name="report")
app.command(session_app, name="session")
app.command(work_app, name="work")
app.command(models_app, name="models")
app.command(streaming_app, name="streaming")
app.command(config_app, name="config")
app.command(workspace_app, name="workspace")
app.command(completion_app, name="completion")
