# Meridian-Channel Behaviors

**Status:** Approved

This document specifies exact user-facing behaviors and command syntax. When in doubt about what should happen, refer here.

## Space Lifecycle

### Creating a Space

**Command:**
```bash
meridian space start [--name <name>] [--model <model>] [--autocompact <n>]
```

**Behavior:**
1. Creates new space with auto-generated ID (e.g., `w145`)
2. If `--name` provided, stores in `space.md`
3. Creates directory structure: `.meridian/w145/{agents,skills,fs,index.json,space.md}`
4. Registers primary agent (harness determines model if not overridden)
5. Creates session lock at `.meridian/active-spaces/w145`
6. Launches harness with space context via environment variables
7. Returns space ID and connection info to harness

**Exit behavior:**
- If harness closes without explicit `meridian space close`, agent can call `meridian space resume`
- Lock is held until `meridian space close` is called or timeout expires (default: 24 hours)

**Example:**
```bash
$ meridian space start --name "novel-draft-v2" --model claude-opus-4-6

Space w145 started (novel-draft-v2)
Primary agent: claude-opus-4-6
Session ID: sess-claude-001
Ready to accept runs.

# Harness now launches with:
export MERIDIAN_SPACE_ID=w145
export MERIDIAN_AGENT_NAME=primary
export MERIDIAN_PRIMARY_AGENT=true
export MERIDIAN_SPACE_ROOT=/repo/.meridian/spaces/w145
```

### Resuming a Space

**Command:**
```bash
meridian space resume [--space-id <id>] [--fresh] [--model <model>]
```

**Behavior:**
1. If `--space-id` omitted, resumes most-recent active space
2. If `--space-id` and space doesn't exist, error
3. Reads `space.md` to get space metadata
4. If `--fresh` provided, terminates existing session and starts new one
5. Otherwise, connects to existing session (reuses harness if still running)
6. Loads agent profile, skills, and context
7. Returns ready-to-continue state

**Example:**
```bash
# Resume most recent space
$ meridian space resume
Space w145 resumed (novel-draft-v2)
Session: sess-claude-001
Context loaded.

# Resume specific space
$ meridian space resume --space-id w145
Space w145 resumed (novel-draft-v2)

# Start fresh harness for same space
$ meridian space resume --space-id w145 --fresh --model gpt-5.3-codex
Space w145 resumed (novel-draft-v2)
Session: sess-codex-001
Harness: Codex
Ready.
```

### Listing Spaces

**Command:**
```bash
meridian space list [--limit <n>]
```

**Behavior:**
1. Reads `index/spaces.json` (regenerated from `.meridian/spaces/*/space.md`)
2. Returns most recent `<n>` spaces (default: 10)
3. Includes ID, name, state, last activity time
4. Shows active spaces marked with `*`

**Example:**
```bash
$ meridian space list
ID    Name                     State    Last Activity
w148  *novel-draft-v2          active   2025-02-28 12:15
w147  auth-refactor            paused   2025-02-28 11:30
w146  research-project         completed 2025-02-27 09:00
w145  outline-v1               abandoned 2025-02-26 14:20
```

### Showing Space Details

**Command:**
```bash
meridian space show <space-id>
```

**Behavior:**
1. Reads `<space-id>/space.md` and `<space-id>/agents/*.md`
2. Lists agents, skills, pinned files
3. Shows run history summary
4. Shows filesystem structure (top-level dirs)

**Example:**
```bash
$ meridian space show w145
ID:              w145
Name:            novel-draft-v2
State:           active
Created:         2025-02-28 10:30:00 UTC
Primary Agent:   alice (claude-opus-4-6)
Pinned Files:
  - fs/outline/v2.md
  - fs/characters/main.md

Agents:
  alice (primary) - Researcher and planner
  bob - Writing specialist
  carol - Editor

Skills:
  research, writing, editing, review

Filesystem:
  fs/
  ├── outline/ (2 files, 15 KB)
  ├── characters/ (5 files, 45 KB)
  ├── chapters/ (8 files, 120 KB)
  └── feedback/ (3 files, 25 KB)

Recent Runs:
  run-2025-02-28-001: alice - "Research character backstory"
  run-2025-02-28-002: bob - "Write chapter 1 opening"
  run-2025-02-28-003: carol - "Edit for flow"
```

### Closing a Space

**Command:**
```bash
meridian space close <space-id>
```

**Behavior:**
1. Verifies space exists
2. Kills any active session locks
3. Transitions space state from `active` → `paused` or `completed`
4. Saves final state to `space.md`
5. Creates git commit with all fs/ changes
6. Removes from `.meridian/active-spaces/`

**Example:**
```bash
$ meridian space close w145
Space w145 closed (paused)
Committed 23 files to git.
Git message: "meridian: close space w145 (novel-draft-v2)"
```

## Agent Spawning

### Spawning a Child Agent

Child agents are launched from within a space by a running agent.

**Command (from within agent context):**
```bash
meridian run --agent <name> [--model <model>] [--skill <skill>] <prompt>
```

**Behavior:**
1. Reads `agents/<name>.md` if it exists; creates stub profile if not
2. If `--model` provided, uses that; otherwise uses agent profile's model
3. Initializes run in `.meridian/runs/run-<timestamp>/`
4. Sets environment variables:
   ```bash
   MERIDIAN_SPACE_ID=<parent-space-id>
   MERIDIAN_AGENT_NAME=<name>
   MERIDIAN_PRIMARY_AGENT=false
   MERIDIAN_PARENT_AGENT=<parent-name>
   ```
5. Detects harness and launches child agent
6. Streams output until completion
7. Saves output to `.meridian/runs/run-<timestamp>/output.md`
8. Returns run ID and exit code

**Example:**
```bash
# Alice spawning Bob
$ meridian run --agent bob --model gpt-5.3-codex --skill implement "Write JWT implementation"

Agent bob spawned (gpt-5.3-codex)
Skill: implement
Run ID: run-2025-02-28-002

[streaming output...]

Run completed (exit code 0)
Output saved to: runs/run-2025-02-28-002/output.md
```

## Filesystem Operations

All operations are scoped to the current space's `fs/` directory.

### List Files

**Command:**
```bash
meridian fs ls [path]
```

**Behavior:**
1. Lists files in `<space-root>/fs/<path>` (default: `fs/`)
2. Shows size, modification time
3. Returns recursive listing if `--recursive` provided

**Example:**
```bash
$ meridian fs ls
research/ (2 files, 45 KB)
drafts/ (5 files, 120 KB)
feedback/ (1 file, 8 KB)

$ meridian fs ls research/
sources.md (28 KB)
citations.md (17 KB)
```

### Read/Cat File

**Commands:**
```bash
meridian fs cat <path>                    # Print full contents
meridian fs read <path> [--tail <n>]      # Print with context (head/tail options)
```

**Behavior:**
1. Reads `<space-root>/fs/<path>`
2. If file doesn't exist, error with suggestion
3. If binary, shows size and type instead of contents

**Example:**
```bash
$ meridian fs cat research/sources.md
# Research Sources

## Academic Papers
1. Smith et al. (2023) - "Trade Routes in Early Modern Europe"
...

$ meridian fs read drafts/chapter1.md --tail 20
Last 20 lines of drafts/chapter1.md:

The merchant nodded slowly.
...
```

### Write File

**Command:**
```bash
meridian fs write <path> [<content>]
```

**Behavior:**
1. Creates or overwrites `<space-root>/fs/<path>`
2. If content not provided on command line, reads from stdin
3. Creates parent directories if they don't exist
4. Returns file size and path

**Example:**
```bash
$ meridian fs write research/summary.md <<EOF
# Research Summary

Key findings:
- X led to Y
- Z was unexpected
EOF

Wrote 89 bytes to: fs/research/summary.md
```

### Copy/Move Files

**Commands:**
```bash
meridian fs cp <src> <dst>                # Copy file or directory
meridian fs mv <src> <dst>                # Move/rename
```

**Behavior:**
1. Validates source exists
2. If source is directory and `--recursive` not provided, error
3. Creates parent directories in destination
4. Overwrites destination if exists (with warning)
5. Returns operation summary

**Example:**
```bash
$ meridian fs cp research/ research-backup/
Copied 2 files (45 KB) to: fs/research-backup/

$ meridian fs mv chapters/old-v1.md chapters/v1-archive/v1.md
Moved: fs/chapters/old-v1.md → fs/chapters/v1-archive/v1.md
```

### Delete Files

**Command:**
```bash
meridian fs rm <path> [--recursive]
```

**Behavior:**
1. Removes file or directory
2. If directory and `--recursive` not provided, error
3. Cannot undelete (warns agent)

**Example:**
```bash
$ meridian fs rm chapters/draft.md
Removed: fs/chapters/draft.md

$ meridian fs rm /tmp/junk --recursive
Removed directory: fs/tmp/junk (5 files, 12 KB)
```

### Make Directory

**Command:**
```bash
meridian fs mkdir <path>
```

**Behavior:**
1. Creates directory and all parents
2. If already exists, no error (idempotent)

**Example:**
```bash
$ meridian fs mkdir chapters/part1/subpart1
Created: fs/chapters/part1/subpart1/
```

## Session Management

### Session Environment Variables

When an agent starts in a space, it receives:

```bash
# Set by Meridian
MERIDIAN_SPACE_ID=w145
MERIDIAN_AGENT_NAME=bob
MERIDIAN_PRIMARY_AGENT=false
MERIDIAN_PARENT_AGENT=alice
MERIDIAN_SPACE_ROOT=/repo/.meridian/spaces/w145
MERIDIAN_SESSION_ID=sess-codex-001

# Set by harness
CLAUDE_API_KEY=...          # Only if Claude
CODEX_API_KEY=...           # Only if Codex
OPENCODE_CLI_PATH=...       # Only if OpenCode
```

### Checking Session Status

**Command:**
```bash
meridian space show <space-id>
```

**Behavior:**
1. Shows current session info
2. Shows active agent (if session is active)
3. Shows last activity time

**Example:**
```
Session:         sess-claude-001
Harness:         claude-opus-4-6
Active:          true
Last Activity:   2025-02-28 12:15:00 UTC
Agent:           alice (primary)
```

### Persistence

Session state is **not persistent**:
- Harness closes → Session data is lost
- Can resume space with new harness and session
- Old session files are archived in `.meridian/sessions/<old-id>/`

## Workflow Examples

### Example 1: Researcher → Coder → Reviewer (Sequential)

```bash
# User starts the space
$ meridian space start --name "auth-refactor" --model claude-opus-4-6

# Claude (alice) spawns researcher job
$ meridian run --agent researcher --skill research \
  "Analyze current JWT implementation and document all edge cases"

[Alice reads output]
$ meridian fs cat fs/research/jwt-analysis.md

# Alice spawns implementer (Codex is faster for coding)
$ meridian run --agent implementer --model gpt-5.3-codex --skill implement \
  "Implement new JWT strategy based on fs/research/jwt-analysis.md.
   Output code to fs/implementation/"

[Waits for Codex to finish]

# Alice spawns reviewer (Opus for thoroughness)
$ meridian run --agent reviewer --model claude-opus-4-6 --skill review \
  "Review code in fs/implementation/ for security issues and test coverage"

# Alice summarizes findings
$ meridian fs write fs/SUMMARY.md <<'EOF'
## Auth Refactor Summary

**Research:** Completed
- Edge cases: 12 identified
- Risk: Medium

**Implementation:** Completed
- Lines changed: 453
- Files modified: 8

**Review:** Completed
- Issues found: 3 critical, 2 minor
- Recommendation: Ready for staging with minor fixes

## Next Steps
1. Address 3 critical issues
2. Run integration tests
3. Deploy to staging
EOF

$ meridian space close w145
```

### Example 2: Parallel Agents (Multi-harness)

```bash
# User starts space with Claude
$ meridian space start --name "content-generation" --model claude-opus-4-6

# Claude (primary) coordinates work
$ meridian run --agent writer1 --model claude-sonnet-4-6 \
  "Write blog post draft on AI ethics"

$ meridian run --agent writer2 --model gpt-5.3-codex \
  "Write code examples for AI ethics post"

$ meridian run --agent illustrator --model opencode \
  "Create ASCII diagrams showing AI decision trees"

# Agents write to fs/blog-draft/, fs/code-examples/, fs/diagrams/
# Claude can read all outputs and assemble final post

$ meridian fs cat fs/blog-draft/outline.md
$ meridian fs cat fs/code-examples/example1.py
$ meridian fs cat fs/diagrams/decision-tree.txt

$ meridian fs write fs/FINAL-POST.md <<'EOF'
# AI Ethics: A Guide

[assembled content from all agents]
EOF
```

### Example 3: Organizing Work with Filesystem

```bash
# Space created, research underway
$ meridian fs mkdir analysis/{market,competitive,internal}
$ meridian fs mkdir drafts/{v1,v2,v3}
$ meridian fs mkdir feedback/{alice,bob,carol}
$ meridian fs mkdir decisions/

# Agents organize their work
$ meridian fs write analysis/market/report.md "..."
$ meridian fs write analysis/competitive/landscape.md "..."
$ meridian fs write drafts/v1/outline.md "..."

# Agent pinning important files for visibility
$ meridian space show w145 | grep "Pinned Files"
  - fs/decisions/arch-choice.md
  - fs/analysis/market/summary.md
  - fs/drafts/v1/outline.md

# Another agent reviews decisions
$ meridian fs cat fs/decisions/arch-choice.md
$ meridian fs write fs/feedback/alice/decision-review.md \
  "Looks good, but consider X for Y reasons"
```

### Example 4: Continued Work Across Harnesses

```bash
# Day 1: Claude starts work
$ meridian space start --name "documentation" --model claude-opus-4-6
$ meridian run --agent planner --skill plan "Create doc outline"
[Claude writes to fs/outline/]
$ meridian space resume --space-id w145
[Claude continues working]
$ exit

# Day 2: OpenCode picks up work
$ meridian space resume --space-id w145 --fresh --model opencode
# OpenCode reads fs/outline/ and continues where Claude left off
$ meridian fs cat fs/outline/structure.md
# Writes completed docs to fs/content/
$ meridian space close w145
```

## Error Messages and Recovery

### Missing MERIDIAN_SPACE_ID

**Behavior:**
```bash
$ meridian run --agent bob "Do work"
Error: MERIDIAN_SPACE_ID not set

To work in a space, set the environment variable:
  export MERIDIAN_SPACE_ID=<space-id>

Or start a new space:
  meridian space start --name <optional-name>

Or resume a space:
  meridian space resume
```

### Space Not Found

**Behavior:**
```bash
$ meridian space show w999
Error: Space 'w999' not found

Available spaces:
  w145 (novel-draft-v2)
  w146 (auth-refactor)
  w147 (research-project)
```

### Filesystem Path Out of Bounds

**Behavior:**
```bash
$ meridian fs cat ../../etc/passwd
Error: Path traversal detected

Paths must be within fs/ directory.
Path requested: ../../etc/passwd
Resolved to: /etc/passwd (outside space)

Use relative paths like:
  meridian fs cat research/notes.md
```

### Lock Timeout

**Behavior:**
```bash
$ meridian space resume w145
Error: Space w145 is locked by another session

Session: sess-claude-001 (started 48 hours ago)
To force-resume, use:
  meridian space resume w145 --fresh

Or check if harness is still running:
  meridian space show w145
```
