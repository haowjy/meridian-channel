# Test Architecture Overhaul — Plan v4

**Revision:** Fix ownership gaps, shared infra lane, branch-isolated execution

---

## Key Changes from v3

1. **Shared infrastructure lane first** — Lane 0 owns fakes.py, fixtures.py, all conftest.py
2. **Branch-isolated execution** — Each lane works on isolated branch, integrates after green
3. **Explicit catch-all lane** — Lane G handles anything audit marks REWRITE outside core lanes
4. **Audit constrains lanes** — Phase 0 output includes lane assignment, not just classification
5. **Archive retention policy** — Keep through stabilization, move to docs/ as reference after

---

## Research Reference

All coders and reviewers MUST read these before writing/reviewing tests:

1. **Test Desiderata (Kent Beck):** isolated, deterministic, fast, writable, readable, behavioral, structure-insensitive, predictive
2. **Functional Core / Imperative Shell:** Pure logic in core (test without mocks), I/O in thin shell (integration tests)
3. **Pytest Conventions:** Directory-based markers, fixture scoping, conftest.py hierarchy
4. **Injectable Seams:** Use FakeClock, FakeHeartbeat, FakeSpawnRepository — NO monkeypatching privates

Research artifacts:
- `.meridian/work/test-architecture-overhaul/requirements.md` (sections on best practices)
- `tests/support/fakes.py` (available test doubles)

---

## Current State

| Directory | Count | Quality |
|-----------|-------|---------|
| tests/unit/ | ~87 | Mixed — some monkeypatch-heavy |
| tests/integration/ | ~459 | Mostly good |
| tests/contract/ | ~82 | Parity tests |
| tests/platform/ | ~13 | OS-specific |
| tests/support/ | — | Fakes/fixtures |

---

## Phase 0: Audit & Assign (1 coder)

Classify every test file AND assign lane ownership:

| Classification | Lane | Action |
|----------------|------|--------|
| GOOD | — | Keep in place |
| MISCLASSIFIED | — | Move to correct dir (in-place fix) |
| REWRITE | A-G | Archive + rewrite by assigned lane |
| DUPLICATE | — | Delete outright |

**Output:** `tests/_audit.md` with:
```
| File | Classification | Lane | Reason |
|------|----------------|------|--------|
| tests/unit/harness/test_lifecycle.py | REWRITE | D | Monkeypatches connection internals |
| tests/unit/state/test_events.py | GOOD | — | Pure function test, already correct |
```

**Constraint:** Every REWRITE file MUST have a lane assigned. If no lane fits, assign to Lane G (catch-all).

---

## Phase 1: Shared Infrastructure (Lane 0)

**Owner:** Single coder, merges to main before other lanes start

**Scope:**
- `tests/support/fakes.py` — Extend/fix fakes as needed
- `tests/support/fixtures.py` — Shared fixtures
- `tests/conftest.py` — Root config
- `tests/unit/conftest.py` — Unit markers
- `tests/integration/conftest.py` — Integration markers
- `tests/contract/conftest.py` — Contract markers

**Exit criteria:** All shared infra stable, main green, other lanes can branch from here.

---

## Phase 2: Parallel Rewrite (Lanes A-G)

Each lane branches from main (post-Phase 1), works in isolation.

### Lane A: State & Persistence
- `spawn_store.py`, `session_store.py`, `work_store.py`
- `reaper.py` — reconciliation
- `events.py` — pure reducer (verify, likely GOOD)
- `paths.py`, `liveness.py`

### Lane B: Streaming & Execution
- `streaming_runner.py` — using FakeHeartbeat, FakeClock
- `decision.py` — pure function (verify, likely GOOD)
- `errors.py` — retry classification
- `spawn_manager.py`

### Lane C: Process Launch
- `process/runner.py` — launcher selection
- `process/pty_launcher.py` — PTY (platform)
- `process/subprocess_launcher.py` — artifact capture
- `process/session.py`

### Lane D: Harness Connections
- `harness/claude.py`, `harness/codex.py`, `harness/opencode.py`
- Workspace projection tests
- Connection lifecycle tests

### Lane E: CLI & Bootstrap
- `cli/bootstrap.py` — command dispatch
- `cli/primary_launch.py` — launch policy
- `cli/main.py` — integration

### Lane F: Contract & Parity
- Verify/update contract tests
- Add contracts for new seams
- Drift detection tests

### Lane G: Catch-All
- `ops/` — spawn operations
- `config/` — configuration loading
- `catalog/` — model catalog
- `platform/` — OS-specific (may stay as-is)
- Anything else audit assigns

---

## Phase 3: Per-Lane Review (parallel)

Each lane reviewer checks:
- [ ] No monkeypatching private internals (e.g., `_HEARTBEAT_INTERVAL_SECS`)
- [ ] Uses fakes where appropriate (pure functions don't need fakes)
- [ ] Behavior-named tests (`test_spawn_records_failure_when_...`)
- [ ] Correct classification (unit = no I/O, integration = I/O)
- [ ] Archived tests' behaviors are covered or explicitly dropped with reason
- [ ] Branch green before merge

**Merge order:** Lanes can merge independently once reviewed + green. No cross-lane dependencies after Phase 1.

---

## Phase 4: Integration

1. All lanes merged to main
2. Full test suite green
3. CI markers working (`pytest -m unit`, `pytest -m integration`)
4. Runtime targets met

---

## Phase 5: Stabilization & Archive Retention

1. Keep `tests/_archived/` for 1 sprint after full green
2. Move to `docs/archived-tests/` as permanent reference (not collected by pytest)
3. Document in README which archived tests were intentionally not replaced and why

---

## Success Criteria

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Private monkeypatches in unit/ | 0 | `grep -r "monkeypatch.*_[A-Z]" tests/unit/` |
| Unit tests with tmp_path | 0 | `grep -r "tmp_path" tests/unit/` → should be 0 or integration |
| Spawn lifecycle coverage | start→running→finalize→terminal | Named test exists for each transition |
| Reconciliation coverage | orphan detection, reaper fix-up | Named tests exist |
| Process launch coverage | PTY, subprocess, artifact capture | Named tests exist |
| Harness connect coverage | connect, interrupt, cancel, resume | Named tests exist |
| Unit runtime (CI) | <30s | `time pytest -m unit` |
| Full runtime (CI) | <90s | `time pytest` |
| All lanes reviewed | ✓ | Review spawn succeeded for each |

---

## Execution Diagram

```
Phase 0 (audit)
    ↓
Phase 1 (shared infra - Lane 0)
    ↓ merge to main
Phase 2 (parallel branches)
    Lane A ─branch─→ rewrite → Review A → merge
    Lane B ─branch─→ rewrite → Review B → merge
    Lane C ─branch─→ rewrite → Review C → merge
    Lane D ─branch─→ rewrite → Review D → merge
    Lane E ─branch─→ rewrite → Review E → merge
    Lane F ─branch─→ rewrite → Review F → merge
    Lane G ─branch─→ rewrite → Review G → merge
    ↓
Phase 4 (integration - all merged)
    ↓
Phase 5 (stabilization)
```

---

## For Impl-Orchestrator

When spawning coders for each lane, MUST pass:
1. This plan (PLAN-V4.md)
2. Research reference: `.meridian/work/test-architecture-overhaul/requirements.md`
3. Audit output: `tests/_audit.md`
4. Lane-specific archived tests from `tests/_archived/`
5. Current fakes: `tests/support/fakes.py`

Each coder must READ the research sections on Test Desiderata, functional core/imperative shell, and pytest conventions BEFORE writing tests.
