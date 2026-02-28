# Session Handoff: Meridian-Channel Reframing

## Current Status

✅ **Setup Complete** — meridian-channel is now self-contained with full context and documentation for the reframing work.

## What's Been Set Up

### Directory Structure
```
meridian-channel/
├── CLAUDE.md                      # Philosophy + dev conventions (sparse, focused)
├── HANDOFF.md                     # This file
├── README.md                      # Updated with philosophy + core concepts
├── .claude/                       # Skills, hooks, agent definitions (copied)
├── .agents/                       # Skills mirror (copied)
├── src/meridian/                  # Main codebase
├── tests/                         # Test suite (247 tests, all passing)
│
└── ARCHITECTURE.md                # Complete system design
    BEHAVIORS.md                   # User-facing behavior specs
    CODEX-BLOCKERS.md              # Upstream feature gaps (Codex/OpenCode)
    IMPLEMENTATION-GAPS.md         # 8 component analyses with priorities
    IMPLEMENTATION-PLAN.md         # 5-phase plan (8-10 weeks)
    MERIDIAN-CHANNEL.md            # 1,305-line mega-document (TL;DR of all above)
    VISION.md                      # High-level vision (1-2 year goal)
    WHAT-TO-REMOVE.md              # Deprecated code inventory
    MVP-SCOPE.md                   # Claude-first strategy with blocker tracking
```

### Key Philosophy (Recap)

Meridian is a **coordination layer**, not a file system/project manager/execution engine:

1. **Harness-Agnostic**: Same `meridian` commands work across Claude, Codex, OpenCode, Cursor, **etc.** for both primary agents and subagents
2. **Files as Authority**: `.meridian/<space-id>/` markdown files are source of truth; SQLite optional index only
3. **Explicit Over Implicit**: MERIDIAN_SPACE_ID required; no auto-creation
4. **Agent Profiles Own Skills**: Static skill definitions, loaded fresh on launch (survives context compaction)
5. **Minimal Constraints**: Agents organize `.meridian/<space-id>/fs/` however they want

## Available Skills

All 7 meridian-collab skills copied to `.claude/skills/`:
- `researching` — Codebase exploration
- `reviewing` — Code review
- `run-agent` — Agent execution engine
- `orchestrate` — Multi-model task composition
- `plan-task` — Task decomposition
- `mermaid` — Diagram validation
- `scratchpad` — Scratch code conventions

## Current Implementation Status

### ✅ Complete
- Agent profiles with `allowed_tools` field (fine-grained permissions)
- ExplicitToolsResolver + factory (per-harness tool mapping)
- Run preparation integration (wired in _run_prepare.py)
- Space launch integration (wired in launch.py)
- All tests passing (247 tests, 19 agent profile tests)
- Bundled profiles fixed (workspace-write → space-write, terminology updated)

### ❌ Not Yet Started
- Phase 0: Validation Audit (compare current implementation vs. ARCHITECTURE.md)
- Phase 1: CLI Refactoring (implement `meridian fs` commands)
- Phase 2: Space Metadata Migration (SQLite → `.meridian/<space-id>/space.md` files)
- Phase 3: JSON Index (optional simplification)
- Phase 4: Harness Integration Testing (E2E with Claude/Codex/OpenCode)
- Phase 5: Documentation & Examples

## Immediate Next Steps

### Option 1: Start Phase 0 (Recommended)
**Validation Audit** — Understand current divergences from documented target
- Audit meridian-channel code against ARCHITECTURE.md/BEHAVIORS.md
- Document gaps (which ones are high/medium/low priority)
- Identify blockers that prevent Phase 1
- Estimated: 1-2 weeks
- Use `/run-agent researching` to explore current implementation

### Option 2: Start Phase 1
**CLI Refactoring** — Implement `meridian fs` commands
- Add 8 new commands: `ls`, `cat`, `read`, `write`, `cp`, `mv`, `rm`, `mkdir`
- Requires understanding current space CRUD layer
- Estimated: 2 weeks
- Blocked by: None (can proceed in parallel with Phase 0)

### Option 3: Create Full Documentation
**Recreate VISION.md, ARCHITECTURE.md, etc.** if they're needed immediately
- All content is in MERIDIAN-CHANNEL.md mega-document (1,305 lines, 45-60 min read)
- Individual docs exist: VISION.md, ARCHITECTURE.md, BEHAVIORS.md, etc.
- Just need review + refinement before implementation

## Key Decision: MVP Strategy

**MVP Definition**: Full meridian-channel working with Claude Code
- Codex/OpenCode supported with documented fallbacks
- Tracked blockers in CODEX-BLOCKERS.md for upstream features
- Claude-first: fastest validation, no workarounds needed

## Important Files & Paths

### Documentation (All in this directory)
- **MERIDIAN-CHANNEL.md** — Start here for complete overview
- **IMPLEMENTATION-PLAN.md** — 5 phases with timelines & decision gates
- **CODEX-BLOCKERS.md** — Upstream feature gaps (living doc)
- **MVP-SCOPE.md** — Harness support matrix + strategy

### Implementation
- **src/meridian/lib/ops/_run_prepare.py** — Run creation/validation (already uses build_permission_resolver)
- **src/meridian/lib/space/launch.py** — Space supervisor launch (already uses build_permission_resolver)
- **src/meridian/lib/safety/permissions.py** — Permission resolvers (ExplicitToolsResolver already implemented)
- **src/meridian/cli/space.py** — Space CLI commands (where `meridian fs` group needs to be added)
- **src/meridian/lib/config/agent.py** — Agent profile parsing (allowed_tools already parsed)

### Tests
- **tests/test_default_agent_profiles.py** — 19 comprehensive agent profile tests (all passing)
- Run all: `uv run pytest` (247 tests pass)

## Git Status

### Changes Staged/Ready to Commit
- `meridian-channel/CLAUDE.md` — New philosophy-focused dev guide
- `meridian-channel/README.md` — Updated with philosophy + core concepts
- `meridian-channel/src/meridian/resources/.agents/agents/agent.md` — Fixed sandbox (workspace-write → space-write)
- `meridian-channel/src/meridian/resources/.agents/agents/supervisor.md` — Updated terminology, cleaned skills
- Copied `.claude/` and `.agents/` from root for self-contained development

### Documentation Moved
- `_docs/meridian-channel/` → `meridian-channel/` (VISION.md, ARCHITECTURE.md, BEHAVIORS.md, etc.)
- Root README.md cleaned (removed Agent Coordination section, moved to meridian-channel/README.md)

## Session Context Summary

Previous work:
1. Designed complete meridian-channel reframing with 9 documentation files
2. Identified deprecated code (--skills flag, SQLite as authority, skill composition)
3. Tracked upstream blockers (Codex/OpenCode feature gaps)
4. Defined MVP scope (Claude-first, tracked fallbacks)
5. Fixed bundled profiles + terminology alignment
6. Set up self-contained submodule with full skills/agents support

## What NOT to Do

- ❌ Don't work from root directory context—focus on meridian-channel
- ❌ Don't implement features without reviewing relevant phase section in IMPLEMENTATION-PLAN.md
- ❌ Don't modify SQLite schema before Phase 2 decision gate
- ❌ Don't remove `--skills` flag before Phase 1 plan is approved (deprecated but still used)

## Recommended Next Conversation

Start with: "Let's begin Phase 0 (Validation Audit)—can you audit the current implementation against ARCHITECTURE.md?"

This will:
1. Identify what's already correct
2. Surface gaps that block Phase 1
3. Prioritize work within 5-phase plan
4. Build confidence in the documented architecture

---

**Last Updated**: 2026-02-28
**Status**: Ready for Phase 0 (Validation Audit)
**Test Status**: All 247 tests passing ✅
