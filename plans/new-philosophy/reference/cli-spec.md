# Meridian CLI Specification

**Status:** Post-refactor target state (2026-02-28) — describes the intended final state, not current code

This document defines the complete post-refactor state: directory layout, CLI commands, MCP mapping, human vs agent modes, and the rationale behind each design choice.

---

## Directory Layout

```
.meridian/
├── agents/                         # User-authored agent profiles (YAML markdown)
├── skills/                         # User-authored project skills
├── config.toml                     # User-authored settings (models, harness config)
├── .gitignore                      # Auto-created on first space creation
└── .spaces/                        # Runtime state (dot-prefix = machine-managed)
    ├── .lock                       # Global lock for space ID generation
    └── <space-id>/                 # e.g. s3/
        ├── space.lock              # Per-space lock for space.json read-modify-write
        ├── space.json              # Space metadata (`schema_version: 1`, gitignored)
        ├── runs.lock               # Lock for runs.jsonl appends + run ID generation
        ├── runs.jsonl              # Append-only run events (gitignored)
        ├── sessions.lock           # Lock for sessions.jsonl appends (gitignored)
        ├── sessions.jsonl          # Session start/stop events (gitignored)
        ├── sessions/               # Liveness locks (gitignored)
        │   └── <session-id>.lock   # flock held by each harness process
        ├── runs/                   # Run artifacts (gitignored, never cleaned)
        │   └── <run-id>/
        │       ├── input.md
        │       └── output/
        └── fs/                     # Agent working directory (COMMITTED)
```

### Why this layout

| Path | Category | Purpose |
|------|----------|---------|
| `agents/` | User-authored | Agent profiles — checked into git, edited by humans |
| `skills/` | User-authored | Domain knowledge/capabilities — checked into git |
| `config.toml` | User-authored | Settings — checked into git |
| `.spaces/` | Runtime | Dot-prefix separates from user-authored content. Prevents future namespace collisions (e.g. if `spaces/` is ever user-facing) |
| `.spaces/.lock` | Global lock | Serializes space ID generation |
| `space.lock` | Per-space lock | Serializes `space.json` read-modify-write operations |
| `space.json` | Runtime state | Machine-managed JSON (`schema_version: 1` in MVP). Not config (not YAML/TOML), not documentation (not markdown). Read/write in place |
| `runs.lock` | Append lock | Serializes run ID generation + `runs.jsonl` appends |
| `runs.jsonl` | Append-only log | One JSON line per run event. Never edited, only appended |
| `sessions.jsonl` | Append-only log | One JSON line per session event. Tracks concurrent harness processes and continuation defaults (`harness_session_id`, `harness`, `model`, `params`). Appends are serialized with `flock` on `sessions.lock` |
| `sessions.lock` | Append lock | Shared lock file used for all `sessions.jsonl` appends |
| `sessions/*.lock` | Liveness | OS-level flock. Blocked = alive, acquirable = dead/crashed |
| `runs/<run-id>/` | Artifacts | Run inputs/outputs. Never auto-cleaned. Agents grep over them |
| `fs/` | Work product | The only committed content inside `.spaces/`. Agent working directory |

`runs.jsonl` event examples:

```json
{"v":1,"event":"start","id":"r1","session_id":"c1","model":"gpt-5.3-codex","agent":"coder","harness":"codex","harness_session_id":"<codex conversation id>","status":"running","started_at":"2026-02-28T10:00:00Z","prompt":"..."}
{"v":1,"event":"finalize","id":"r1","status":"succeeded","exit_code":0,"duration_secs":128,"total_cost_usd":0.042,"input_tokens":4200,"output_tokens":1800,"finished_at":"2026-02-28T10:02:08Z"}
{"v":1,"event":"finalize","id":"r2","status":"failed","exit_code":1,"error":"Token limit exceeded","duration_secs":45,"finished_at":"2026-02-28T10:02:53Z"}
```

`space.json` minimum schema (MVP):

```json
{"schema_version":1,"id":"s3","name":"feature-auth","status":"active","started_at":"2026-02-28T10:00:00Z","finished_at":null}
```

### Gitignore

Auto-created at `.meridian/.gitignore` on first space creation:

```gitignore
.spaces/**
!.spaces/*/
!.spaces/*/fs/
!.spaces/*/fs/**
```

**Effect:** Everything in `.spaces/` is gitignored except `fs/` content. Runtime state stays local, work product gets committed.

### Environment variables

```bash
MERIDIAN_SPACE_ID=<space-id>    # Required context for space-scoped operations
MERIDIAN_SPACE_FS=<repo>/.meridian/.spaces/<space-id>/fs  # Direct path for shell-capable agents
MERIDIAN_SESSION_ID=<chat-id>  # Current chat alias (c1, c2...), set by meridian start, used by run continue
MERIDIAN_HARNESS_COMMAND=<command>  # Resolved harness CLI command (e.g. claude, codex), set by meridian start
```

---

## Two Audiences, One Binary

`meridian` serves two audiences from a single binary. It detects which mode to use based on `MERIDIAN_SPACE_ID`:

### Human mode (no `MERIDIAN_SPACE_ID`)

The user is at their terminal managing spaces and launching agents. They see all commands. Output defaults to human-readable text.

```
$ meridian -h
Usage: meridian [command]

Launch:
  start            Auto-resolve active space (new chat), or create one if none active
                   --new                Force create a new space
                   --space <space-id>   Use explicit space (new chat by default)
                   --continue [chat-id] Continue last or specific chat

Space management:
  space list       List all spaces
  space show       Show space details and session history
  space close      Close a space and clean up sessions

Runs:
  run spawn        Start a new agent run (new conversation)
  run continue     Continue a previous run's conversation
                   [run-id]             If omitted, continues last run in current chat
  run list         List runs
  run show         Show run details
  ...

Configuration:
  config show      Show current config

Utilities:
  init             Initialize .meridian/ directory
  doctor           Check and repair space health
  serve            Start MCP server
  completion       Shell completion setup

Tip: When MERIDIAN_SPACE_ID is set (e.g. via meridian start),
only agent-relevant commands are shown. Use --human for full help.
```

### Agent mode (`MERIDIAN_SPACE_ID` is set)

An LLM inside a harness session. It sees only what it needs. Output defaults to JSON for programmatic piping.

```
$ meridian -h
Usage: meridian [command]

Runs:
  run spawn        Start a new agent run (new conversation)
  run continue     Continue a previous run's conversation
                   [run-id]             If omitted, continues last run in current chat
  run list         List runs
  run show         Show run details
  run stats        Aggregate run statistics
  run wait         Wait for running runs

Discovery:
  skills list      List available skills
  skills show      Show skill details
  models list      List available models
  models show      Show model details

Health:
  doctor           Check and repair space health
```

**Hidden flag:** `--human` forces full human-mode help. This flag is:
- Never shown in agent-mode help
- Documented only in human-mode help and docs
- An escape hatch, not a feature agents should know about

### Why this split matters for LLMs

1. **Less noise** — an LLM reading help output shouldn't see `start` (it's already in a space) or `config show` (not its job) or `completion install` (irrelevant)
2. **Smaller tool surface** — fewer MCP tools = less confusion, faster tool selection
3. **Right affordances** — the commands an agent sees are exactly the ones it should use
4. **No foot-guns** — an agent can't accidentally `space close` or `config` something it shouldn't

---

## CLI Commands

### Launch (human mode only)

These commands are **never exposed via MCP**. They launch/manage harness processes, which makes no sense over MCP.

| Command | What it does |
|---------|-------------|
| `meridian start` | If `start.auto_resume=true` (default), auto-resolve last active space and start a fresh chat there; if no active space exists, create a new space. Launch primary agent via `subprocess.Popen` (no pipes — child inherits terminal directly for full interactive passthrough) + `wait()`. Sets `MERIDIAN_SPACE_ID`, `MERIDIAN_SPACE_FS`, `MERIDIAN_SESSION_ID`, and `MERIDIAN_HARNESS_COMMAND` in child env. Runs stale-session cleanup and acquires session flock. |
| `meridian start --new` | Force create a new space and start a fresh chat (overrides auto-resolve). |
| `meridian start --space <space-id>` | Use explicit existing space, start a fresh chat/conversation. |
| `meridian start --continue` | Auto-resolve last active space, continue its last chat. |
| `meridian start --continue <chat-id|harness-session-id>` | Resolve across spaces and continue a specific chat alias (for example `c2`) or raw harness session ID. |
| `meridian start --space <space-id> --continue` | Optional disambiguation: use explicit space, continue its last chat. |
| `meridian start --space <space-id> --continue <chat-id|harness-session-id>` | Optional disambiguation: resolve only within explicit space. |

When continuation is requested, Meridian resolves the session target from `sessions.jsonl`:
- `--continue` with no value: last chat in last active space
- `--continue <chat-id>`: search across spaces for alias
- `--continue <harness-session-id>`: search across spaces for raw harness session ID
- `--space <space-id>` limits lookup to that space (optional disambiguation, not required)

Continuation errors and constraints:
- `ERROR [AMBIGUOUS_SESSION]: Chat c2 exists in multiple spaces. Next: use --space to disambiguate.`
- `ERROR [HARNESS_MISMATCH]: Session c2 was started with Claude. Cannot continue with a Codex model. Next: pick a model on Claude or omit -m.`
- Continuation is harness-locked to the original session record (`harness`); model changes are allowed only within that harness.

Passthrough behavior:
- Original session `params` are baseline defaults.
- Explicit passthrough flags (`--system-prompt`, `--append-system-prompt`, `-m`, etc.) override/add on top.
- Unsupported flags warn and are ignored, for example: `WARNING [UNSUPPORTED_FLAG]: --append-system-prompt is not supported by Codex. Next: remove this flag or switch to a harness that supports it. Flag ignored.`
- Meridian passes resolved `harness_session_id` through harness-native continuation flags (`--resume <id>` for Claude, `resume <id>` for Codex, `--session <id>` for OpenCode).
When `meridian start` auto-resolves a space, emit:

```
WARNING [SPACE_AUTO_RESUMED]: Resumed active space s3 ("feature-auth"). Next: use --new to start a fresh space.
```

Model/agent/skills flags pass through independently of `--space`/`--continue`/`--new`.

### Space management (human mode only)

| Command | What it does |
|---------|-------------|
| `meridian space list` | Scan `.meridian/.spaces/*/space.json`, print table of spaces with status. |
| `meridian space show <space-id>` | Read space.json, show details + session history (flock liveness check) with chat aliases (`c1`, `c2`, ...). Includes copy-paste `meridian start --space <id> --continue <chat-id>` commands for each chat. |
| `meridian space close <space-id>` | Update space.json status to closed, stop all tracked sessions, cleanup lock files. |

### Run lifecycle (agent + human, MCP: yes)

| Command | CLI | MCP tool | What it does |
|---------|-----|----------|-------------|
| Spawn run | `meridian run spawn` | `run_spawn` | Append start event to runs.jsonl, create runs/<id>/ dir, launch agent in a new conversation. |
| Continue run | `meridian run continue [run-id]` | `run_continue` | Continue a previous run's harness conversation. With `run-id`, continue that specific run. Without `run-id`, continue the last run from current chat (`MERIDIAN_SESSION_ID`). |
| List runs | `meridian run list` | `run_list` | Parse runs.jsonl, filter by status/model/agent |
| Show run | `meridian run show` | `run_show` | Find run by ID in runs.jsonl, show details + artifacts |
| Run stats | `meridian run stats` | `run_stats` | Aggregate from runs.jsonl: cost, duration, counts |
| Wait | `meridian run wait` | `run_wait` | Block until running run(s) finish |

**Auto-create behavior:** If an agent runs `meridian run spawn` without `MERIDIAN_SPACE_ID`, meridian auto-creates a space and warns:

```
WARNING [SPACE_AUTO_CREATED]: No MERIDIAN_SPACE_ID set. Created space s5. Next: set MERIDIAN_SPACE_ID=s5 for subsequent commands.
```

This is ergonomic for simple single-run workflows without being invisible magic — the agent is told what happened and what to do next.

**Only `run spawn` auto-creates.** All other commands (`run continue`, `run list`, `skills list`, etc.) error without `MERIDIAN_SPACE_ID` — they need existing space context.

### Skills and models (agent + human, MCP: yes)

| Command | CLI | MCP tool | What it does |
|---------|-----|----------|-------------|
| List skills | `meridian skills list` | `skills_list` | Scan `.meridian/skills/` directory |
| Show skill | `meridian skills show` | `skills_show` | Read skill file, show contents |
| List models | `meridian models list` | `models_list` | List available models from config |
| Show model | `meridian models show` | `models_show` | Show model details from config |

No `skills reindex` — there's no index. It's a directory scan every time. At this scale (dozens of skills) it's instant.

### Health (agent + human, MCP: yes)

| Command | CLI | MCP tool | What it does |
|---------|-----|----------|-------------|
| Doctor | `meridian doctor` | `doctor` | Four jobs: (1) sweep stale session locks, (2) detect orphaned runs and append synthetic finalize, (3) reconcile stale `space.json` status, (4) detect missing/corrupt `space.json`, report warning, and skip that space (no recreate) |

`doctor` is the canonical name, not a shortcut to `diag repair`. Both humans and agents benefit from "is my space healthy?".

### Configuration (human mode only)

| Command | MCP | What it does |
|---------|-----|-------------|
| `meridian config show` | No | Show current config.toml settings |
| `meridian init` | No | Create `.meridian/` and scaffold a self-documenting `config.toml` with all options present but commented out |

Config conventions:
- Merge order (later wins): (1) built-in defaults, (2) base `config.toml`, (3) override config from `--config` or `MERIDIAN_CONFIG` when supplied.
- `meridian start` auto-resume behavior is controlled by `[start].auto_resume` (default `true`). Explicit `--continue` still resolves a continuation target.
- `meridian init` writes all config keys commented out, with defaults shown as comments so users uncomment only what they want to override.

Example generated `config.toml`:

```toml
# Meridian configuration
# Uncomment and modify options to override defaults.

# [start]
# auto_resume = true

# [harness]
# default = "claude"
```

Not agent-relevant. Agents don't manage configuration.

### Utilities (human mode only)

| Command | MCP | What it does |
|---------|-----|-------------|
| `meridian init` | No | Create `.meridian/` directory with default structure |
| `meridian serve` | No | Start MCP server (exposes agent-mode commands as tools) |
| `meridian completion` | No | Shell completion setup (bash/zsh/fish/install) |

### Top-level commands

| Command | What it does |
|---------|-------------|
| `meridian start` | Top-level launch command (not a shortcut — standalone command with `--new`, `--space`, and `--continue` flags) |
| `meridian doctor` | Standalone health check and repair |

No ambiguous shortcuts (`list`, `show`, `wait`) — users type `meridian space list` and `meridian run show` explicitly. Less convenient, less confusing.

---

## MCP Surface

`meridian serve` starts the MCP server. **Only agent-mode commands are registered as MCP tools:**

| MCP tool | Maps to |
|----------|---------|
| `run_spawn` | `meridian run spawn` |
| `run_continue` | `meridian run continue [run-id]` |
| `run_list` | `meridian run list` |
| `run_show` | `meridian run show` |
| `run_stats` | `meridian run stats` |
| `run_wait` | `meridian run wait` |
| `skills_list` | `meridian skills list` |
| `skills_show` | `meridian skills show` |
| `models_list` | `meridian models list` |
| `models_show` | `meridian models show` |
| `doctor` | `meridian doctor` |

**Not exposed as MCP:**
- `start` / `space list/show/close` — these launch/manage harness processes, meaningless over MCP
- `config show` — human concern
- `init`, `serve`, `completion` — infrastructure commands

**Total: 11 MCP tools.** Small, focused, no noise.
MCP tool responses MAY include an optional human-readable `"warning"` field; when no warning exists, the field is omitted (not `""`, not `null`).

---

## Deleted Commands

| Command | Why deleted |
|---------|------------|
| `meridian migrate run` | No SQLite → no migrations |
| `meridian export space` | No SQLite export needed; fs/ is already committed |
| `meridian skills reindex` | No index to rebuild; directory scan every time |
| `meridian space read` | Cut — agents use shell or harness file tools under `$MERIDIAN_SPACE_FS/` |
| `meridian space write` | Cut — agents use shell or harness file tools under `$MERIDIAN_SPACE_FS/` |
| `meridian space files` | Cut — agents use shell or harness file tools under `$MERIDIAN_SPACE_FS/` |
| `meridian fs read/write/ls` | Cut — Meridian is a coordination layer; agents use `$MERIDIAN_SPACE_FS/` directly |
| `meridian space start` | Replaced by `meridian start` (top-level command) |
| `meridian space resume` | Replaced by `meridian start` with `--new`/`--space`/`--continue` variants |
| `meridian run retry` | Cut from MVP — users manually retry with `run spawn` |
| `meridian context list` | Cut from MVP — agent already has `MERIDIAN_SPACE_ID` in env |
| `meridian context pin` | Cut from MVP — agents manage context explicitly |
| `meridian context unpin` | Cut from MVP — agents manage context explicitly |

---

## Output Format

Output format varies by mode:
- **Agent mode** (`MERIDIAN_SPACE_ID` set): CLI defaults to JSON for programmatic piping. No `--json` flag needed — mode detection handles it.
- **Human mode** (no `MERIDIAN_SPACE_ID`): CLI defaults to human-readable text/tables. Compact, minimal tokens.
- **MCP tools**: Flat JSON responses (inherent to MCP protocol). No nested metadata wrappers.
- **CLI warnings/diagnostics**: stderr only. Never mixed into stdout.
- **MCP warning convention**: MCP tool responses MAY include a human-readable `"warning"` field. If no warning exists, the field is omitted (not `""`, not `null`).
- **MCP warning example**: `{"id": "r5", "status": "running", "warning": "WARNING [SPACE_AUTO_CREATED]: No MERIDIAN_SPACE_ID set. Created space s5. Next: set MERIDIAN_SPACE_ID=s5 for subsequent commands."}`
- **Why warning is in MCP JSON**: stderr is invisible over MCP, so auto-create warnings must be carried in MCP response payloads.
- **Error messages**: Follow `[CODE] + cause + next action` format. Example: `ERROR [SPACE_REQUIRED]: No MERIDIAN_SPACE_ID set. Next: run 'meridian run spawn' to auto-create a space.`

Example `run_list` JSON response (agent mode or MCP):
```json
[
  {"id": "r1", "status": "succeeded", "model": "opus-4-6", "duration_secs": 128, "cost_usd": 0.04},
  {"id": "r2", "status": "running", "model": "gpt-5.3-codex"}
]
```

## Why This Is Simple for an LLM

1. **~10 commands in agent help** — an LLM can read the entire help output in one shot and know everything it can do
2. **Predictable structure** — `meridian <group> <action>`. No surprises, no interactive prompts
3. **JSON output in agent mode** — structured, parseable, pipeable. No fragile text parsing
4. **Environment-driven context** — `MERIDIAN_SPACE_ID`, `MERIDIAN_SPACE_FS`, `MERIDIAN_SESSION_ID`, and `MERIDIAN_HARNESS_COMMAND` are set once by the launcher. The agent never has to discover or construct paths
5. **No hidden state** — everything is files the agent can read. `space.json`, `runs.jsonl`, and `sessions.jsonl` are directly inspectable from the space directory alongside `$MERIDIAN_SPACE_FS/`
6. **Auto-create on `run spawn`** — if an agent runs without `MERIDIAN_SPACE_ID`, `run spawn` makes one and tells you. Other commands error clearly
7. **No index/cache invalidation** — no SQLite means no "did you run reindex?" moments. Data is always fresh because it's read from files
8. **Actionable errors** — `[CODE] + cause + next action` format tells agents exactly what went wrong and what to do next

---

## Roadmap

### MVP (current plan): File-based foundation + CLI
- `meridian start` → `subprocess.Popen` (no pipes, child inherits terminal) + `wait()` — full interactive passthrough, then cleanup on exit
- Context-aware help, MCP surface = agent commands only
- All state in files (space.json, runs.jsonl, sessions.jsonl)

### V2: Web UI — multi-session manager
- `meridian serve` expands to REST + websocket API (serves both MCP clients and web UI)
- Web dashboard: create spaces, spawn sessions, view runs/costs
- Embedded terminal panes (xterm.js) with direct PTY passthrough per harness session
- User clicks "Add Session" → API spawns harness with PTY → renders in browser terminal pane
- Harness doesn't know it's in a browser — it's just a PTY
- CLI stays unchanged for agents and terminal-preferring humans

### Why skip a CLI REPL
- The web UI solves multi-session management better than a REPL ever could
- Terminal multiplexing is a solved problem (tmux) — no need to reinvent it in the CLI
- Building a REPL is throwaway work if the UI is coming
- `meridian start` stays dead simple: auto-resolve/create space based on flags, launch one harness, done
