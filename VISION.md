# Meridian-Channel Vision

**Status:** Approved

## What is Meridian-Channel?

Meridian-Channel is a **coordination and communication layer** for multi-agent systems. It enables AI agents (Claude, Codex, OpenCode) to collaborate within self-contained spaces by managing shared metadata, agent lifecycle, and a git-friendly working filesystem. Meridian is not a file system, data storage engine, or execution runtime — it's the nervous system that lets agents understand each other and coordinate work.

## Core Philosophy

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

## End Goal (1-2 Years Out)

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

## User Experience

### A Writer Using Meridian

```bash
# Start a collaborative writing space
meridian space start --name "novel-draft-v2"
# → Launches Claude as primary agent
# → User directs Claude to: analyze current draft, outline gaps, suggest edits

# Spawn a specialist agent for research
meridian run --agent researcher "Find 3 sources on 1850s trade routes"
# → Claude calls meridian run to spawn Codex
# → Codex researches, writes findings to .meridian/spaces/<id>/fs/research/

# Resume with a different harness
meridian space resume --model gpt-5.3-codex
# → Codex picks up where Claude left off
# → Reads same space context, same working files
# → Continues writing draft iteration

# Check what agents have done
meridian fs ls .meridian/spaces/novel-draft-v2/fs/
# → Shows all agent work: outlines/, research/, drafts/, feedback/

# Close and commit
meridian space close novel-draft-v2
# → Triggers git commit of all work
```

### A Software Engineer Using Meridian

```bash
# Start refactoring effort
meridian space start --name "auth-refactor"

# Researcher gathers context
meridian run --agent researcher --skill research "Map current auth flow"

# Implementation specialist takes over
meridian run --agent implementer --model gpt-5.3-codex "Write JWT implementation"

# Reviewer checks work
meridian run --agent reviewer --model claude-opus-4-6 "Review auth changes for security"

# All agents read/write to same space, same filesystem
# Human merges agent-written code into codebase
```

## Harness Agnosticism

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

This abstraction makes agents truly composable: a researcher trained on Claude can be spawned by Codex without modification, and a reviewer running in OpenCode can review Codex work without friction.
