---
detail: standard
audience: developer, architect
---
# ws-transport-v2 Stage 1: Agent Headcount and Orchestration

## Orchestration Model

**Primary orchestrator**: Claude Opus (this conversation) -- exercises ultimate judgment on all decisions, resolves conflicts between reviewers, approves merges between phases. NEVER writes implementation code directly.

**Implementation**: via `meridian spawn -a coder -m codex` -- one implementer at a time per worktree to avoid merge conflicts.

**Code review**: via `meridian spawn -a reviewer -m gpt` -- 2-3 reviewers per phase, fanned out in parallel with different review angles.

**Unit testing**: via `meridian spawn -a unit-tester -m gpt` -- writes focused unit tests to verify correctness, runs them, reports results. Tests are marked with `[unit-tester]` comments so orchestrator can decide keep vs discard.

**Smoke testing**: via `meridian spawn -a smoke-tester -m sonnet` -- QA agent that writes disposable curl/WS scripts to test from the outside like a real user. Scripts go in `scratch/smoke/` (gitignored).

**Tracking**: orchestrator appends to `implementation-log.md` after each spawn report -- decisions, weird findings, backlog items, bugs.

## Execution Workflow (per phase)

```
1. Orchestrator composes implementation prompt
   - References: design docs (-f), existing code (-f), previous findings
   - Clear scope boundaries: one phase, specific files
   |
   v
2. meridian spawn -m codex -a coder -p "Phase N: ..." -f [context files]
   - Wait for completion: meridian spawn wait <id>
   - Read report: meridian spawn show <id>
   |
   v
3. Orchestrator evaluates implementation report
   - Check: did it follow the design? any deviations?
   - Log weird findings to implementation-log.md
   |
   v
4. Fan out 2-3 reviewers (parallel)
   meridian spawn -m gpt -a reviewer -p "Review Phase N: correctness" -f [files]
   meridian spawn -m gpt -a reviewer -p "Review Phase N: Go idioms" -f [files]
   meridian spawn wait <id1> <id2>
   |
   v
5. Orchestrator synthesizes review findings
   - CRITICAL -> must fix before approve
   - MEDIUM -> orchestrator decides (fix or defer)
   - LOW -> log to implementation-log.md, move on
   |
   v
6. If issues: spawn targeted fix + re-review (max 3 cycles)
   If clean: commit, update plan status, move to next phase
```

## Per-Phase Staffing

### Phase 0: Foundation (~400 lines)
- 1x `meridian spawn -a coder -m codex` -- session manager fixes + authenticator refactor + error sentinels
- 1x `meridian spawn -a reviewer-solid` -- SOLID, code consistency
- 1x `meridian spawn -a reviewer-concurrency` -- singleflight + refcount race analysis
- 1x `meridian spawn -a unit-tester` -- verify singleflight + refcount guards with race tests
- 1x `meridian spawn -a reviewer-planning` -- does Phase 0 set up Phase 1A/1B correctly?
- 1x `meridian spawn -a documenter -m haiku` then `-m opus` -- update design docs if implementation deviated
- Gate: orchestrator approves, all existing + new tests pass

### Phase 1A: Document WS Handler (~700 lines)
- 1x `meridian spawn -a coder -m codex` -- new document handler + registry
- 1x `meridian spawn -a reviewer-solid` -- SOLID, consistency with existing handlers
- 1x `meridian spawn -a reviewer-concurrency` -- connection lifecycle, goroutine leaks
- 1x `meridian spawn -a reviewer-security` -- auth, origin, rate limits, frame size
- 1x `meridian spawn -a unit-tester` -- handler tests: handshake, heartbeat, limits
- 1x `meridian spawn -a smoke-tester` -- connect to /ws/documents/{id}, bad auth, oversized frames
- 1x `meridian spawn -a reviewer-planning` -- API shape right for Phase 3 frontend?
- 1x `meridian spawn -a documenter -m opus` -- update feature docs, API contract
- Gate: orchestrator approves, Yjs handshake works

### Phase 1B: Project WS Simplification (~800 lines)
- 1x `meridian spawn -a coder -m codex` -- strip binary/subscription, split broadcast
- 1x `meridian spawn -a reviewer-solid` -- clean separation of JSON vs binary paths
- 1x `meridian spawn -a reviewer-concurrency` -- broadcast fanout, connection registry
- 1x `meridian spawn -a unit-tester` -- proposal routing tests, verify binary rejection
- 1x `meridian spawn -a reviewer-planning` -- proposal flow intact for existing frontend?
- 1x `meridian spawn -a documenter -m opus` -- update proposal event docs
- Gate: orchestrator approves, proposals work correctly
- NOTE: runs in parallel with 1A via git worktree

### Phase 2: Cleanup (~300 net lines)
- 1x `meridian spawn -a coder -m codex` -- delete dead code, update interfaces
- 1x `meridian spawn -a reviewer-solid` -- dead code, unused imports, interface hygiene
- Gate: build passes, all tests pass

### Phase 3: Frontend (~1000 lines)
- 1x `meridian spawn -a coder -m codex` -- DocumentSessionManager + hook rewrites
- 1x `meridian spawn -a reviewer-solid` -- React/TS patterns, store consistency
- 1x `meridian spawn -a reviewer-concurrency` -- async interleaving, warm pool lifecycle
- 1x `meridian spawn -a smoke-tester` -- open document in browser, test warm pool transitions
- 1x `meridian spawn -a reviewer-planning` -- does the frontend match the backend API?
- 1x `meridian spawn -a documenter -m opus` -- final doc sweep: feature docs, api-events-contract, README
- Gate: pnpm build + lint pass

## Agent Profiles

All agents defined in `.claude/agents/`. Use with `meridian spawn -a <name>`.

### Builders

| Agent | Default Model | Purpose |
|-------|---------------|---------|
| `coder` | gpt-5.3-codex | Write production code, follow SOLID |
| `researcher` | gpt-5.3-codex | Read-only codebase exploration + web search |

### Reviewers

Each reviewer type has a distinct focus area and system prompt. This prevents the "review everything" problem where findings are shallow across all areas.

| Agent | Default Model | Focus |
|-------|---------------|-------|
| `reviewer-solid` | gpt-5.4 | SOLID principles, code style, project consistency, correctness |
| `reviewer-concurrency` | gpt-5.4 | Races, deadlocks, lock ordering, goroutine leaks |
| `reviewer-security` | gpt-5.4 | Auth bypass, input validation, rate limiting, resource exhaustion |
| `reviewer-planning` | claude-opus-4-6 | Long-term architecture alignment, design doc drift, future-proofing |

### Testers

| Agent | Default Model | Purpose |
|-------|---------------|---------|
| `unit-tester` | gpt-5.4 | Write focused unit tests, run them. Most tests are disposable -- only keep regression guards. |
| `smoke-tester` | claude-sonnet-4-6 | QA from outside -- curl, WS clients, race probes in `scratch/smoke/` |

### Documentation

| Agent | Default Model | Purpose |
|-------|---------------|---------|
| `documenter` | claude-opus-4-6 | Keeps docs in sync with code changes. Uses `documenting` + `mermaid` skills. |

Two-pass usage:
- **Discovery** (cheap): `meridian spawn -a documenter -m haiku -p "Find all docs affected by Phase N changes"`
- **Writing** (quality): `meridian spawn -a documenter -m opus -p "Update these docs: ..."`

## Parallel Work Strategy

Phases 1A and 1B can run in parallel using **git worktrees**:
- Main worktree: Phase 1A (document WS handler)
- Worktree branch: Phase 1B (project WS simplification)
- Both branch from the Phase 0 commit
- Merge both into the feature branch before Phase 2

Within a single worktree, work is SEQUENTIAL (one implementer at a time). Parallel reviewers are read-only.

## Orchestrator Responsibilities

1. **Compose prompts** -- detailed, scoped, with correct -f context files
2. **Evaluate reports** -- never blindly accept; check against design docs
3. **Synthesize reviews** -- resolve reviewer conflicts, make final calls
4. **Track everything** -- append to `implementation-log.md` after each spawn:
   - Decisions made (even small ones)
   - Weird things the implementer found
   - Backlog items for later
   - Bugs discovered but not fixing now
5. **Manage phase gates** -- approve completion, trigger next phase
6. **Exercise ultimate judgment** -- reviewers advise, orchestrator decides
7. **Commit after each phase** -- testable state, clear commit message
