# Dev Workflow Testing Overhaul

**Status:** Draft  
**Date:** 2026-04-19  
**Related:** test-architecture-overhaul (research foundation)

---

## Problem Statement

The current meridian-dev-workflow has testing gaps:

1. **impl-orch skips or does superficial smoke testing** — focused on "make code work", testing is afterthought
2. **Regression testing is implicit** — relies on existing pytest coverage, no explicit "what else might break?"
3. **Unit tests are ad-hoc** — added by coders without design thinking, no coherent architecture
4. **No separation of concerns** — coder thinks "does my code work?" but testing requires "how can this break?"

---

## Proposed Workflow

### Current Flow

```
design-orch → impl-orch (code + verify + maybe smoke) → docs-orch
```

### Proposed Flow

```
research/requirements
  → design-orch (iterate with user)
  → impl-orch:
      per phase:
        coder(s) + verifier (internal, flexible)
        → phase exit gate:
            → smoke-tester (mandatory)
            → regression-check (mandatory)
  → unit-test-orch (design test architecture)
  → docs-orch
```

---

## Key Concepts

### Phase vs Subphase

| Concept | Definition | Testing |
|---------|------------|---------|
| **Phase** | Testable unit of functionality, defined by planner | Smoke + regression at phase exit |
| **Subphase** | Internal implementation detail, impl-orch's discretion | Verifier only (fast feedback) |

**Contract:** Phases are testable boundaries. How coder breaks down work is implementation detail.

### Three Testing Concerns

| Type | Question | When | Who |
|------|----------|------|-----|
| **Smoke testing** | "Does the new code work?" | Phase exit | smoke-tester |
| **Regression testing** | "Did we break existing functionality?" | Phase exit | regression-checker (or smoke-tester with regression focus) |
| **Unit test design** | "Will we know when it breaks later?" | After impl complete | unit-test-orch |

---

## impl-orch Changes

### Current Phase Structure

```
per phase:
  spawn coder
  spawn verifier
  [smoke-tester optional, often skipped]
  next phase
```

### Proposed Phase Structure

```
per phase:
  coder work (may be subphases internally)
  verifier (runs frequently, fast feedback)
  
  PHASE EXIT GATE (mandatory, blocks progress):
    smoke-tester:
      - Test new functionality works
      - Real CLI invocations, not mocked
      - Adversarial mindset: "how can this break?"
      - Integration boundaries get special attention
    
    regression-check:
      - What else touches the code I changed?
      - What functionality shares these code paths?
      - Test adjacent functionality still works
      - Not just pytest — behavioral verification
  
  next phase
```

### Phase Exit Criteria

Phase is NOT complete until:
1. ✅ Verifier passes (pyright, ruff, pytest)
2. ✅ Smoke-tester confirms new functionality works
3. ✅ Regression-check confirms existing functionality unbroken

---

## New Agent: unit-test-orch

### Purpose

Design and implement proper test architecture AFTER implementation is complete and working.

### When It Runs

After impl-orch completes all phases successfully.

### What It Does

1. **Analyze implementation** — What was built? What are the testable units?
2. **Design test architecture** — Apply Test Desiderata, functional core/imperative shell
3. **Create fixtures** — Shared fakes (FakeClock, FakeRepository, etc.)
4. **Write unit tests** — Pure logic tests, regression guards, edge cases
5. **Organize tests** — Proper directory structure (unit/integration/contract)

### Mindset

Not "does it work?" (that's smoke testing)
But "will we know when it breaks?" (regression guards, documentation of behavior)

### Research Foundation

Applies principles from test-architecture-overhaul research:
- Kent Beck's Test Desiderata
- Gary Bernhardt's functional core/imperative shell
- pytest fixture conventions
- Behavior-oriented test naming

---

## Prompt Updates Required

### 1. impl-orchestrator

Add to phase execution:

```markdown
## Phase Exit Gate

Every phase MUST pass exit gate before proceeding:

1. **Smoke Test (mandatory)**
   - Spawn smoke-tester with phase deliverables
   - Real CLI/integration testing, not mocked
   - Phase blocks until smoke-tester passes
   
2. **Regression Check (mandatory)**
   - What existing functionality might be affected?
   - Test adjacent code paths still work
   - Phase blocks until regression check passes

Do NOT proceed to next phase until both pass.
```

### 2. smoke-tester (update existing)

Add adversarial mindset prompting:

```markdown
## Mindset

You are an adversary, not a validator. Your job is to BREAK things.

- Don't just test the happy path
- Test edge cases, error conditions, boundary values
- Test integration boundaries (CLI, subprocess, file I/O, network)
- Ask: "What inputs would break this?"
- Ask: "What state would cause unexpected behavior?"
```

### 3. New: regression-checker (or add to smoke-tester)

```markdown
## Regression Check

After code changes, verify existing functionality still works.

1. Identify what code paths were touched
2. Identify what OTHER functionality uses those paths
3. Test that adjacent functionality still works
4. This is behavioral verification, not just running pytest

Ask:
- "What else calls the functions I modified?"
- "What features share state with what I changed?"
- "What was working before that might not work now?"
```

### 4. New: unit-test-orch

```markdown
## Unit Test Orchestrator

Design and implement proper test architecture after implementation.

### Principles
- Test Desiderata: isolated, deterministic, fast, writable, readable, predictive
- Functional core / imperative shell: test pure logic extensively, thin integration tests
- Behavior naming: test_spawn_times_out_and_returns_retryable_error
- Fixture discipline: shared fakes, factory fixtures, explicit over autouse

### Process
1. Analyze what was implemented
2. Identify pure logic that should be unit tested
3. Design fixtures for testability (FakeClock, FakeRepository)
4. Write unit tests with proper structure
5. Organize into tests/unit/, tests/integration/

### Output
- New test files in proper locations
- Shared fixtures in tests/support/
- Marker-based organization
```

---

## Workflow Documentation Update

Update dev-orchestrator to reflect new flow:

```markdown
## Workflow

1. **Requirements capture** — Clarify scope, constraints, success criteria
2. **Design** — Spawn design-orch, iterate until approved
3. **Implementation** — Spawn impl-orch with mandatory smoke + regression per phase
4. **Unit test design** — Spawn unit-test-orch to create proper test architecture
5. **Documentation** — Spawn docs-orch to update docs
```

---

## Success Criteria

1. **No skipped smoke tests** — impl-orch blocks on phase exit gate
2. **Regression thinking is explicit** — Not just "run pytest" but "what might break?"
3. **Unit tests have architecture** — Not ad-hoc, but designed with fixtures and structure
4. **Separation of concerns** — Coder implements, testers test with adversarial mindset

---

## Implementation Plan

### Phase 1: Update impl-orchestrator prompt

- Add phase exit gate section
- Make smoke + regression mandatory
- Add blocking language ("do NOT proceed until...")

### Phase 2: Update smoke-tester prompt

- Add adversarial mindset prompting
- Add integration boundary focus
- Add edge case / error condition emphasis

### Phase 3: Add regression-check capability

Option A: New regression-checker agent
Option B: Add regression focus to smoke-tester prompt
(Decide based on whether concerns should be separated)

### Phase 4: Create unit-test-orch

- New agent profile
- Apply test-architecture-overhaul research
- Focus on design, not just writing tests

### Phase 5: Update dev-orchestrator

- Document new workflow
- Add unit-test-orch to routing

### Phase 6: Update workflow documentation

- AGENTS.md in meridian-dev-workflow repo
- Skill documentation

---

## Files to Modify

In `meridian-dev-workflow` repo:

| File | Change |
|------|--------|
| `agents/impl-orchestrator/AGENT.md` | Add phase exit gate, mandatory smoke + regression |
| `agents/smoke-tester/AGENT.md` | Add adversarial mindset, edge case focus |
| `agents/unit-test-orch/AGENT.md` | New agent |
| `agents/dev-orchestrator/AGENT.md` | Update workflow documentation |
| `skills/agent-staffing/resources/testers.md` | Add unit-test-orch |

---

## Open Questions

1. **Regression-checker: separate agent or smoke-tester enhancement?**
   - Separate = clearer responsibility
   - Combined = less orchestration overhead
   
2. **unit-test-orch model selection?**
   - Needs design thinking, not just code generation
   - Probably higher-tier model

3. **How does unit-test-orch interact with existing tests?**
   - Refactor existing tests into proper structure?
   - Or only add new tests and leave existing alone?
