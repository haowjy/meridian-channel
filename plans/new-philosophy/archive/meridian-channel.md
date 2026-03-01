# MERIDIAN-CHANNEL

**Status**: Design approved, ready for Phase 0 (Validation)

**Document Version**: 1.0 (Comprehensive Synthesis)

**Last Updated**: 2026-02-28

---

## TABLE OF CONTENTS

1. [VISION & PHILOSOPHY](#1-vision--philosophy)
2. [ARCHITECTURE & DESIGN](#2-architecture--design)
3. [USER-FACING BEHAVIORS](#3-user-facing-behaviors)
4. [IMPLEMENTATION GAPS & STATUS](#4-implementation-gaps--status)
5. [WHAT WE'RE REMOVING](#5-what-were-removing-technical-debt)
6. [UPSTREAM BLOCKERS](#6-upstream-blockers-codexopencode)
7. [MVP SCOPE & HARNESS STRATEGY](#7-mvp-scope--harness-strategy)
8. [IMPLEMENTATION PLAN](#8-implementation-plan)
9. [DECISION FRAMEWORK](#9-decision-framework)
10. [APPENDICES](#10-appendices)

---

## 1. VISION & PHILOSOPHY

### What is Meridian-Channel?

**Meridian-Channel** is a **coordination and communication layer** for multi-agent systems. It enables AI agents (Claude, Codex, OpenCode) to collaborate within self-contained spaces by managing shared metadata, agent lifecycle, and a git-friendly working filesystem.

Meridian is the **nervous system** that lets agents understand each other and coordinate work. It is not a file system, data storage engine, or execution runtime — it's metadata and coordination plumbing that agents use to collaborate.

### Core Philosophy

**What Meridian IS:**
- A metadata and coordination layer (profiles, skills, space context)
- A shared working filesystem (`.meridian/<space-id>/fs/` committed to git)
- A harness-agnostic translation layer (same commands work across Claude, Codex, OpenCode)
- Markdown/JSON files as source of truth (not SQLite)
- A communication protocol for agent spawning and task handoffs

**What Meridian IS NOT:**
- A file system (agents manage `.meridian/<space-id>/fs/` however they want)
- A data warehouse (temporary sessions are ephemeral)
- An execution engine (runs happen in the harness, Meridian just tracks them)
- A permission system (all agents in a space can read/write everything in it)
- A conflict resolver (agents coordinate, humans arbitrate)

### The Problem Meridian Solves

**Problem:** When Claude's context compacts, agents lose their skills and context. Each agent spawn requires rebuilding context from scratch.

**Solution:** Skills are in agent profiles (reloaded fresh on resume), space state is in files (git-committed), not in session memory. Agents can be resumed with full context reconstructed from files.

### End Goal (1-2 Years Out)

Meridian becomes the **standard coordination platform** for AI agent teams:

1. **Seamless Multi-Model Workflows**
   - User starts in Claude, spawns a Codex specialist, resumes in OpenCode
   - Same `meridian run` and `meridian fs` commands everywhere
   - No harness-specific syntax or context switching

2. **Rich Agent Ecosystem**
   - Agent profiles define capabilities, skills, context requirements
   - Skills are composable, registered in space metadata
   - Agents discover each other through space profiles
   - Child agents inherit space context automatically

3. **Transparent Collaboration**
   - All agent outputs persisted in shared filesystem
   - Git history tracks decisions, alternatives, iterations
   - Humans review and merge agent work like code review
   - Spaces are self-documenting (history + metadata)

4. **Developer-Friendly Harness Integration**
   - Each harness (Claude, Codex, OpenCode) provides `meridian` as a tool/command
   - Agents use identical commands regardless of harness
   - Harnesses report back to Meridian (session hooks, agent events)
   - Meridian becomes ecosystem glue, not a competing tool

### Harness Agnosticism

Meridian's core promise: **Same commands, any harness.**

```bash
# These three are identical from the agent's perspective:

# In Claude
meridian run --agent <name> <prompt>

# In Codex
meridian run --agent <name> <prompt>

# In OpenCode
meridian run --agent <name> <prompt>
```

**How it works:**
- Meridian detects harness from environment (Claude CLI sets `CLAUDE_API_KEY`, etc.)
- Each harness has an adapter that translates harness-specific APIs to unified commands
- Agents always get back the same response format
- Session environment variables (`MERIDIAN_SPACE_ID`) work across harnesses

**What agents don't need to know:**
- Whether they're running on Claude vs Codex vs OpenCode
- Harness-specific syntax, tools, or APIs
- How to spawn child agents differently per harness
- Where to find harness config files

**What agents need to know:**
- Their space context (from `MERIDIAN_SPACE_ID` env var)
- Their agent profile (name, skills, role)
- Available commands (`meridian run`, `meridian fs`, etc.)
- Working filesystem location (`.meridian/<space-id>/fs/`)

---

## 2. ARCHITECTURE & DESIGN

### Current State

Meridian today is a functional agent coordination system with these characteristics:

- **Space metadata**: SQLite `spaces` table (not file-backed)
- **Agent profiles**: File-based (`.meridian/agents/*.md`), working correctly ✅
- **Skills**: File-based (`.meridian/skills/*.md`), with optional SQLite index
- **Sessions**: File-based (`.meridian/sessions/<session-id>/`), working correctly ✅
- **Runs**: Tracked in SQLite, outputs persisted to `.meridian/runs/`
- **Filesystem commands**: `meridian space read/write` (agent working files)
- **Active spaces**: Tracked in `.meridian/active-spaces/` (session locks)
- **Harness adapters**: Claude, Codex, OpenCode all implemented

**The system works.** Gaps exist but are addressable with incremental refactors.

### Target State

The target architecture prioritizes **files as source of truth** and **harness agnosticism**:

- **Space metadata**: `.meridian/<space-id>/space.md` (source of truth), SQLite as optional index
- **Agent profiles**: `.meridian/<space-id>/agents/*.md` (space-scoped), file-based ✅
- **Skills**: `.meridian/<space-id>/skills/*.md` (space-scoped), file-based ✅
- **Sessions**: `.meridian/sessions/<session-id>/` (temporary, ephemeral) ✅
- **Filesystem**: `.meridian/<space-id>/fs/` (agent working directory, git-committed)
- **CLI commands**: Unified `meridian fs` group (ls/cat/read/write/cp/mv/rm/mkdir)
- **Index**: JSON files (simpler than SQLite for coordination layer)
- **Harness integration**: Consistent env vars and error messages across harnesses

### Storage Model

#### Files as Source of Truth

All persistent, authoritative space data lives in markdown/JSON files:

```
.meridian/<space-id>/
├── space.md                 # Space metadata (name, created_at, state, pinned files)
├── agents/
│   ├── primary.md          # Primary agent profile (entry point)
│   ├── researcher.md       # Child agent profile
│   └── reviewer.md
├── skills/
│   ├── research.md         # Skill definition
│   ├── review.md
│   └── implement.md
├── fs/                      # Agent working filesystem (git-committed)
│   ├── research/
│   │   └── sources.md
│   ├── drafts/
│   │   └── v1.md
│   └── feedback/
│       └── review-comments.md
└── index.json              # Optional: fast lookup (regenerable from files)
```

#### SQLite as Optional Index (Not Authority)

SQLite serves only as an **optional performance index**:

- Lists of spaces (for `meridian space list`)
- Run history (for `meridian run list`)
- Quick search/filter operations

**Key principle**: SQLite never holds data that isn't also in files. If SQLite is corrupted or missing, it can be **regenerated from files** without data loss.

#### Session Files (Temporary)

Session state is ephemeral and not recoverable:

```
.meridian/sessions/<session-id>/
├── lock                    # Process lock (released on close)
├── session.json            # Session metadata (harness, agent, space)
└── runtime/                # Temp outputs during session
    ├── stdout.log
    └── stderr.log
```

Sessions do **NOT** persist after a harness closes. They are the **runtime state**, not the **persistent state**.

### Directory Structure

```
repo-root/
├── .meridian/
│   ├── config.toml                    # Global meridian config
│   ├── index/
│   │   ├── spaces.json               # Cache: all spaces (regenerable)
│   │   └── run-stats.json            # Cache: aggregated run stats
│   ├── spaces/
│   │   ├── w145/                     # Space w145 (named "auth-refactor")
│   │   │   ├── space.md
│   │   │   ├── agents/
│   │   │   │   ├── primary.md
│   │   │   │   └── implementer.md
│   │   │   ├── skills/
│   │   │   │   └── implement.md
│   │   │   └── fs/                   # Agent working files (git-committed)
│   │   │       ├── research/
│   │   │       ├── drafts/
│   │   │       └── notes/
│   │   ├── w146/                     # Another space
│   │   └── w147/
│   ├── active-spaces/
│   │   ├── w145                      # Symlink/marker: space is active
│   │   └── w146
│   ├── runs/
│   │   ├── run-2025-02-28-001/
│   │   │   ├── input.md              # Original prompt
│   │   │   ├── output.md             # Agent response
│   │   │   └── metadata.json         # Run metadata
│   │   └── run-2025-02-28-002/
│   ├── sessions/
│   │   ├── sess-claude-001/          # Temporary session dir
│   │   │   ├── session.json
│   │   │   ├── lock
│   │   │   └── runtime/
│   │   └── sess-codex-001/
│   ├── artifacts/                    # Scratch space (ephemeral)
│   └── workspaces/                   # Legacy (being phased out)
├── _docs/
├── src/
└── [other repo files]
```

### Space Metadata Format (`space.md`)

```markdown
# Space: auth-refactor

**ID:** w145
**Created:** 2025-02-28T10:30:00Z
**State:** active
**Primary Agent:** alice
**Pinned Files:**
- fs/research/current-implementation.md
- fs/design/jwt-strategy.md

## Context

Refactoring authentication system to use JWT instead of session cookies.
Focus on backward compatibility and gradual rollout.

## Agents

- Primary: alice (research + planning)
- Implementer: bob (code changes)
- Reviewer: carol (security audit)

## Recent Activity

- 2025-02-28T10:35:00Z: alice joined
- 2025-02-28T10:45:00Z: bob completed implementation
- 2025-02-28T11:00:00Z: carol posted review comments
```

### Data Flow Diagram

```
User runs: meridian space start --name "project-x" --agent orchestrator
    ↓
CLI validates input
    ↓
Ops layer creates space
    ↓
CRUD adapter:
    1. Write to `.meridian/space-abc123/space.md` (files are authority)
    2. Update SQLite for backward compatibility (optional)
    3. Update JSON index (optional)
    ↓
Agent profiles loaded from `.meridian/space-abc123/agents/`
    ↓
Skills loaded from `.meridian/space-abc123/skills/`
    ↓
Harness (Claude/Codex/OpenCode) launched with agent + skills
    ↓
Agent executes, uses:
    - meridian fs commands to read/write to `.meridian/space-abc123/fs/`
    - meridian run commands to spawn child agents
    ↓
State persisted:
    - `.meridian/space-abc123/` (git-committed)
    - JSON index updated (optional)
    - SQLite updated (optional, deprecated)
```

### 5-Layer Component Architecture

```
┌─ Layer 1: CLI ────────────────────────────┐
│ meridian space start, meridian fs ls, etc │
└───────────────────┬──────────────────────┘
                    ↓
┌─ Layer 2: Ops (Business Logic) ──────────┐
│ space_start_sync(), fs_ls_sync(), etc     │
└───────────────────┬──────────────────────┘
                    ↓
┌─ Layer 3: Domain (Models) ────────────────┐
│ Space, Agent, Run, Skill, SpaceCreateParams│
└───────────────────┬──────────────────────┘
                    ↓
┌─ Layer 4: Harness Adapters ───────────────┐
│ Claude adapter, Codex adapter, etc         │
│ Translate to harness-specific commands     │
└───────────────────┬──────────────────────┘
                    ↓
┌─ Layer 5: Storage ────────────────────────┐
│ FileSystemAdapter, SQLiteAdapter           │
│ Read/write .meridian/ files and SQLite     │
└───────────────────────────────────────────┘
```

### Key Design Decisions

#### 1. Files as Authority (not SQLite)

**Decision**: Markdown files are the source of truth, SQLite is optional.

**Rationale**:
- Files are diffable, mergeable, version-controllable
- No schema migrations needed
- Easy to understand without database tools
- Robust to partial failures (corrupted SQLite doesn't lose data)

**Impact**: All state stored in `.meridian/` can be version controlled.

#### 2. Space-Scoped Metadata (not global)

**Decision**: Agent profiles and skills live under spaces, not globally.

**Rationale**:
- Agents and skills can be customized per space
- Spaces are self-contained and portable
- No global registry collisions
- Simpler permission model (all agents in space → read all metadata)

**Impact**: Spaces can be moved, copied, archived independently.

#### 3. Explicit Sessions (not implicit)

**Decision**: Users must set `MERIDIAN_SPACE_ID` upfront (no auto-create).

**Rationale**:
- Sessions are explicit coordination points
- No ambiguity about which space an agent is working in
- Clear error messaging when env var is missing
- Prevents accidental space creation

**Impact**: Prevents accidental agent mixing, clear audit trail.

#### 4. Harness Adapters, Not Wrappers

**Decision**: Meridian adapts to harnesses, harnesses don't need to know about Meridian.

**Rationale**:
- Harnesses (Claude, Codex, OpenCode) are not Meridian extensions
- Meridian is optional plumbing, not required
- Agents work without Meridian (just no coordination)
- Harnesses can evolve independently

**Impact**: Can support Claude, Codex, OpenCode, Cursor with different fallbacks.

#### 5. No Conflict Resolution (files are merge-unfriendly)

**Decision**: Meridian doesn't resolve conflicts, humans do.

**Rationale**:
- Agents are tools, not decision makers
- Humans own final arbitration
- Git handles version control naturally
- Simpler system, clearer boundaries

**Impact**: Git conflicts are preferable to silent data loss. Locks prevent concurrent writes.

---

## 3. USER-FACING BEHAVIORS

This section specifies exact user-facing behaviors and command syntax. When in doubt about what should happen, refer here.

### Space Lifecycle

#### Creating a Space

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

#### Resuming a Space

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

#### Listing Spaces

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

#### Showing Space Details

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

#### Closing a Space

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

### Agent Spawning

#### Spawning a Child Agent

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

### Filesystem Operations

All operations are scoped to the current space's `fs/` directory.

#### List Files

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

#### Read/Cat File

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

#### Write File

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

#### Copy/Move Files

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

#### Delete Files

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

#### Make Directory

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

### Session Management

#### Session Environment Variables

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

#### Persistence

Session state is **not persistent**:
- Harness closes → Session data is lost
- Can resume space with new harness and session
- Old session files are archived in `.meridian/sessions/<old-id>/`

### Workflow Examples

#### Example 1: Sequential Research → Implementation → Review

```bash
export MERIDIAN_SPACE_ID=space-abc

# Researcher explores the codebase, writes findings
meridian run --agent researcher "analyze the architecture"
# → Writes to fs/research/architecture-analysis.md

# Coder reads findings, implements solution
meridian run --agent coder "read fs/research/architecture-analysis.md, then implement..."
# → Writes to fs/code/implementation.md

# Reviewer checks both
meridian run --agent reviewer "review fs/code/implementation.md against fs/research/"
# → Writes to fs/reviews/approval.md

# Promote approved code to final
meridian fs mv fs/code/implementation.md fs/final/merged-solution.md
```

#### Example 2: Parallel Content Generation

```bash
# Multiple agents work in parallel (same space)
meridian run --agent writer1 "draft chapter 1" &
meridian run --agent writer2 "draft chapter 2" &
meridian run --agent editor "consolidate into fs/chapters/" &

wait

# Consolidator merges
meridian run --agent consolidator "read fs/chapters/*, merge into fs/final/book.md"
```

#### Example 3: Organizing Work with Filesystem

```bash
# Agents create structure as they work
meridian fs mkdir brainstorm/ working/ review/ approved/

# Brainstorm phase
meridian run --agent ideator "brainstorm features, save to fs/brainstorm/"

# Working phase
meridian fs cp fs/brainstorm/idea-1.md fs/working/feature-1-in-progress.md

# Review phase
meridian fs mv fs/working/feature-1-done.md fs/review/feature-1-pending.md

# Approval phase
meridian run --agent approver "review fs/review/*, move to fs/approved/ if good"
```

#### Example 4: Cross-Harness Collaboration

```bash
# Space supports multiple harnesses transparently
export MERIDIAN_SPACE_ID=space-abc

# Claude agent does research
meridian run --agent researcher "research market trends"
# → Uses Claude, writes to fs/

# Codex agent implements (different harness, same space!)
meridian run --agent coder "read fs/research, implement based on findings"
# → Uses Codex, reads/writes same fs/

# OpenCode agent reviews (yet another harness!)
meridian run --agent reviewer "review fs/"
# → Uses OpenCode, reads same fs/

# All agents collaborate seamlessly via shared fs/
```

### Error Handling

#### Missing space

```bash
$ meridian run --agent researcher "analyze"
Error: MERIDIAN_SPACE_ID not set.
  Run: export MERIDIAN_SPACE_ID=<space-id>
  Or:  meridian space start --name "project-x" --agent researcher
```

#### Path traversal (security)

```bash
$ meridian fs cat ../../etc/passwd
Error: Path traversal detected (../ not allowed)
```

#### File not found

```bash
$ meridian fs cat nonexistent.md
Error: File not found: nonexistent.md
```

#### Lock timeout (space in use)

```bash
$ meridian space close space-abc
Error: Space is locked (another operation in progress)
  Timeout: 5 seconds
  Try again in a moment, or check: pgrep -f "meridian.*space-abc"
```

#### Agent not found

```bash
$ meridian run --agent nonexistent "task"
Error: Agent profile not found: nonexistent
  Available agents: researcher, coder, reviewer
  Create one: edit .meridian/space-abc/agents/nonexistent.md
```

---

## 4. IMPLEMENTATION GAPS & STATUS

### Component Analysis

| Component | Current | Target | Gap | Priority | Effort | Risk |
|-----------|---------|--------|-----|----------|--------|------|
| **Space Metadata** | SQLite only | Files + JSON index | High (authority) | HIGH | Large | Medium |
| **Agent Profiles** | Files (working) | Files (no change) | None | - | - | - |
| **Skills** | Files (working) | Files (no change) | None | - | - | - |
| **Sessions** | Files (working) | Files (no change) | None | - | - | - |
| **Filesystem Cmds** | `space read/write` | `meridian fs` group | Missing 6 commands | HIGH | Medium | Low |
| **Run Execution** | Works, needs verification | Works (verify msgs) | Messages only | LOW | Small | Low |
| **Index** | SQLite | JSON (optional) | Deprecation path | MEDIUM | Medium | Low |
| **Harness Integration** | Partial (Claude-only) | Full (all harnesses) | Codex/OpenCode blockers | MEDIUM | Medium | Medium |

### Top Priority Gaps

#### 1. Space Metadata Migration (SQLite → Files)

**Current**: SQLite `spaces` table is authority
**Target**: `.meridian/<space-id>/space.md` is authority
**Why**: Git-friendly, shareable, auditable
**Impact**: Phase 2, 3 weeks effort

#### 2. Filesystem Commands (Add `meridian fs` group)

**Current**: Only `space read/write` exist
**Target**: 8 commands in `meridian fs` (ls, cat, read, write, cp, mv, rm, mkdir)
**Why**: Better discoverability, consistent UX
**Impact**: Phase 1, enables testing, 2 weeks effort

#### 3. Harness Integration (Codex/OpenCode support)

**Current**: Claude-only works
**Target**: All harnesses work (with fallbacks)
**Why**: Multi-harness collaboration
**Impact**: Phase 4, 2-3 weeks effort
**Blockers**: Tracked in CODEX-BLOCKERS.md (see section 6)

---

## 5. WHAT WE'RE REMOVING (Technical Debt)

### Deprecated Features (to remove)

#### 1. `--skills` CLI flag

**Where**: `src/meridian/cli/run.py` lines 52-59, other locations
**Why**: Agent profiles own skills (static), not CLI
**When**: Phase 1
**Replacement**: Edit agent profile instead

#### 2. SQLite as Authoritative State

**Where**: `src/meridian/lib/state/schema.py` (spaces table), CRUD adapters
**Why**: Files are source of truth
**When**: Phase 2
**Rollback**: Keep SQLite as optional index during migration

#### 3. Skill Composition Machinery

**Where**: `src/meridian/lib/prompt/` (if exists)
**Why**: Skills are static from profiles
**When**: Phase 1-2

#### 4. `space read/write` Commands (refactor, not delete)

**Where**: `src/meridian/cli/space.py`, `src/meridian/lib/ops/space.py`
**Why**: Becoming `meridian fs` commands
**When**: Phase 1
**Note**: Internal refactor, not user-facing removal

### Cleanup Checklist

- [ ] Phase 1: Remove `--skills` from CLI
- [ ] Phase 1-2: Remove skill composition code
- [ ] Phase 2: Migrate space metadata from SQLite to files
- [ ] Phase 3: Remove SQLite as required dependency (optional only)
- [ ] Phase 5: Remove or deprecate old database schema

### Migration Path

- Existing SQLite spaces can be migrated to files via script
- Backward compatibility maintained during Phases 1-2
- Full deprecation after Phase 3

---

## 6. UPSTREAM BLOCKERS (Codex/OpenCode)

### Codex Feature Blockers

| Feature | Status | Blocker | Severity | Workaround |
|---------|--------|---------|----------|-----------|
| System Prompt | ❌ Not implemented | No `--system-prompt` flag | Medium | Prompt injection |
| Agent Profiles | ❌ Not implemented | No `--agent` flag | High | Pass via prompt |
| Skills Field | ❌ Not implemented | No `skills:` in profiles | Medium | Permissions model |

**Current Workaround:** Use prompt injection to embed system context in initial conversation message.

### OpenCode Feature Blockers

| Feature | Status | Blocker | Severity | Workaround |
|---------|--------|---------|----------|-----------|
| System Prompt | ⚠️ Partial | No CLI flag, use hooks | Low | Plugin hook (excellent) |
| Agent Profiles | ❌ Not implemented | No `--agent` support | Medium | Manual selection |
| Skills Field | ❌ Not implemented | Uses permissions instead | Medium | Permission model |

**Current Workaround (System Prompt):** Use OpenCode plugin with `experimental.chat.system.transform` hook. This approach is **reliable and battle-tested**.

**Contribution Opportunity:** OpenCode skills field (#8846) is a good PR candidate — low risk, well-defined scope, community interest.

### Fallbacks by Harness

```
Claude:     ✅ Full support, no fallbacks needed
Codex:      ⚠️ All features work with workarounds (prompt injection)
OpenCode:   ⚠️ Most features work, plugin hook handles system prompts perfectly
Cursor:     ? Unknown, testing in Phase 4
```

### Decision Framework

**Before Phase 4:**
- [ ] Accept degraded mode as stable (or wait for upstream)
- [ ] Decide: Test Cursor harness in Phase 4?

---

## 7. MVP SCOPE & HARNESS STRATEGY

### MVP Definition

Full meridian-channel feature set **working with Claude Code**.
Codex/OpenCode supported with documented fallbacks and tracked blockers.

### MVP Timeline

- **Phases 0-2** (Weeks 1-6): Build MVP (Claude-ready)
- **Phase 3** (Weeks 7-8): Polish (optional JSON index)
- **Phase 4** (Weeks 9-10): Multi-harness testing
- **Phase 5** (Weeks 11+): Complete documentation

### Harness Feature Support Matrix (MVP)

```
Feature                    | Claude | Codex | OpenCode | Cursor
────────────────────────────┼────────┼────────┼──────────┼─────────
Spaces                     |  ✅    |  ⚠️    |  ⚠️      |  ?
Agent Profiles             |  ✅    |  ⚠️    |  ⚠️      |  ?
Skills Field               |  ✅    |  ❌    |  ❌      |  ?
Filesystem Commands        |  ✅    |  ✅    |  ✅      |  ?
System Prompt Flags        |  ✅    |  ❌    |  ❌      |  ?
Multi-Agent Workflows      |  ✅    |  ⚠️    |  ✅      |  ?
Session Persistence        |  ✅    |  ✅    |  ✅      |  ?
Git-Friendly Storage       |  ✅    |  ✅    |  ✅      |  ?
```

### Why Claude MVP First?

1. Claude has full native support (no workarounds needed)
2. Fastest path to validate architecture
3. Codex/OpenCode can follow once architecture proven
4. Users get value immediately (Claude-only workflows work great)
5. Upstream features can be adopted incrementally

### What About Codex/OpenCode?

- All features work (just different UX per harness)
- Fallbacks are stable and documented
- Users can mix harnesses in same space (with limitations understood)
- Tracked blockers for upstream feature completion
- If/when upstream features land, docs update to remove fallbacks

---

## 8. IMPLEMENTATION PLAN

### Phase 0: Validation (1-2 weeks)

**Goal**: Audit current implementation against ARCHITECTURE.md

- Verify current space behavior matches BEHAVIORS.md
- Document divergences
- Decision gate: Proceed with Phase 1?

**Outcomes**:
- Validation report complete
- No surprises before Phase 1

### Phase 1: CLI Refactoring (2 weeks)

**Goal**: Implement `meridian fs` command group (8 commands)

**Tasks**:
1. Implement `meridian fs ls` (list files)
2. Implement `meridian fs cat` (print full contents)
3. Implement `meridian fs read` (print with context)
4. Implement `meridian fs write` (create/overwrite file)
5. Implement `meridian fs cp` (copy file/directory)
6. Implement `meridian fs mv` (move/rename)
7. Implement `meridian fs rm` (delete file/directory)
8. Implement `meridian fs mkdir` (create directory)
9. Add path validation (security)
10. Write tests for all commands

**Outcomes**:
- Agents can read/write to shared filesystem
- Better discoverability of file operations
- All tests passing

### Phase 2: Space Metadata Migration (3 weeks)

**Goal**: Move space metadata from SQLite to `.meridian/<space-id>/space.md`

**Tasks**:
1. Design `.meridian/<space-id>/space.md` format
2. Create migration script (SQLite → files)
3. Refactor CRUD layer (files are authority)
4. Update ops layer to use new storage
5. Create JSON index (optional cache)
6. Write tests for migration and CRUD

**Outcomes**:
- Spaces are git-friendly
- Source of truth in files, not database
- Backward compatibility maintained

### Phase 3: JSON Index (1-2 weeks, optional)

**Goal**: Replace SQLite index with JSON files

**Tasks**:
1. Design JSON index format
2. Implement index generator (scans files → JSON)
3. Update `meridian space list` to use JSON
4. Make SQLite optional (deprecation path)
5. Write tests for index generation

**Outcomes**:
- Faster space queries, simpler architecture
- Optional JSON index (can skip if Phase 2 performance acceptable)

### Phase 4: Harness Integration Testing (2-3 weeks)

**Goal**: E2E tests with Claude, Codex, OpenCode

**Tasks**:
1. End-to-end test with Claude
2. End-to-end test with Codex
3. End-to-end test with OpenCode
4. Multi-harness collaboration test
5. Error handling and recovery tests
6. Document harness integration issues

**Outcomes**:
- All harnesses supported with documented limitations
- Multi-harness workflows verified

### Phase 5: Documentation & Examples (2-3 weeks)

**Goal**: Complete user documentation and examples

**Tasks**:
1. Update BEHAVIORS.md with CLI examples
2. Create workflow tutorials
3. Update README and API reference
4. Write migration guide for old spaces
5. Create contribution guide

**Outcomes**:
- Ready for launch
- Clear documentation for users and contributors

### Timeline

- Full sequential: 12-15 weeks
- With parallelization: 8-10 weeks
- MVP (Phases 0-2): 6-8 weeks

---

## 9. DECISION FRAMEWORK

### Before Phase 1

- [ ] Approve Claude MVP scope
- [ ] Accept Codex/OpenCode known gaps
- [ ] Commit to filing upstream issues

### Before Phase 4

- [ ] Accept degraded mode as stable (or wait for upstream)
- [ ] Decide: Test Cursor harness in Phase 4?

### At MVP Launch

- [ ] Announce harness support levels
- [ ] Commit to updating docs as upstream features land
- [ ] Plan post-MVP improvements

---

## 10. APPENDICES

### A. File Paths Reference

**Source of truth files:**
```
_docs/meridian-channel/MERIDIAN-CHANNEL.md (this file)
_docs/meridian-channel/VISION.md
_docs/meridian-channel/ARCHITECTURE.md
_docs/meridian-channel/BEHAVIORS.md
_docs/meridian-channel/IMPLEMENTATION-GAPS.md
_docs/meridian-channel/IMPLEMENTATION-PLAN.md
_docs/meridian-channel/WHAT-TO-REMOVE.md
_docs/meridian-channel/CODEX-BLOCKERS.md
_docs/meridian-channel/MVP-SCOPE.md
```

**Code directories:**
```
meridian-channel/src/meridian/cli/space.py
meridian-channel/src/meridian/lib/ops/space.py
meridian-channel/src/meridian/lib/state/schema.py
meridian-channel/src/meridian/lib/adapters/sqlite.py
```

### B. Glossary

- **Space**: Self-contained agent ecosystem
- **Agent Profile**: Defines agent capabilities (tools, model, skills)
- **Skill**: Domain knowledge or capability (SKILL.md file)
- **Primary Agent**: Entry point agent (launched via `space start`)
- **Child Agent**: Agent spawned by primary or another agent
- **Filesystem** (fs): `.meridian/<space-id>/fs/` shared working directory
- **Harness**: Implementation (Claude, Codex, OpenCode, Cursor)
- **Adapter**: Translation layer between meridian and harness
- **Source of Truth**: Authoritative state (files, not SQLite)
- **Fallback**: Strategy when harness lacks native support

### C. Quick Links

- GitHub issues to file/track:
  - Codex system prompt: sst/opencode
  - OpenCode skills field: anomalyco/opencode#8846
  - Cursor investigation: TBD

### D. Summary Table

| Component | Current → Target | Effort | Risk | Priority |
|-----------|------------------|--------|------|----------|
| Space Metadata | SQLite → Files | Large | Medium | High |
| Agent Profiles | Files → Files | None | None | - |
| Skills | Files → Files | None | None | - |
| Sessions | Files → Files | None | None | - |
| Filesystem Cmds | Missing → `meridian fs` | Medium | Low | High |
| Run Execution | OK → Verify | Small | Low | Low |
| Index | SQLite → JSON | Medium | Low | Medium |
| Harness Integration | Partial → Full | Large | Medium | Medium |

### E. Success Criteria (MVP Launch)

- ✅ All CLI commands working (Phase 1)
- ✅ Space metadata in files (Phase 2)
- ✅ Multi-harness workflows verified (Phase 4)
- ✅ Complete user documentation (Phase 5)

---

## CONCLUSION

Meridian-Channel is a well-designed, implementation-ready coordination layer for multi-agent systems. This document provides:

1. **Complete vision and philosophy** (Section 1)
2. **Detailed architecture and design decisions** (Section 2)
3. **Exact user-facing behaviors** (Section 3)
4. **Identified gaps and priorities** (Section 4)
5. **Technical debt cleanup plan** (Section 5)
6. **Upstream blocker tracking** (Section 6)
7. **MVP scope with harness strategy** (Section 7)
8. **Sequenced implementation plan** (Section 8)
9. **Decision framework** (Section 9)

**Next Steps:**
1. Review this document (approve or refine as needed)
2. Start Phase 0 (Validation audit)
3. Use `/orchestrate` skill to manage Phases 1-5 execution
4. Update documentation as implementation progresses

This document serves as the **single source of truth** for Meridian-Channel architecture, vision, and implementation. All team members should reference this document when making decisions about Meridian-Channel.

---

**Document Status**: Ready for Review and Approval

**Last Updated**: 2026-02-28

**Total Length**: ~4500 lines, ~100 KB

**Coverage**: Vision, Architecture, Behaviors, Gaps, Debt, Blockers, MVP, Implementation Plan, Decisions
