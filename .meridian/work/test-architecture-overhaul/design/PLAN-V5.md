# Test Architecture Overhaul — Plan v5

**Revision:** Fix shared-infra ownership, Lane F sequencing, Windows validation, monkeypatch detection

---

## Key Changes from v4

1. **Shared infra stays open** — Dedicated owner through Phase 2, lanes rebase before merge
2. **Lane F after interface lanes** — Contract tests merge after A-E/G settle
3. **Windows CI gate** — Explicit platform verification in success criteria
4. **Broader monkeypatch detection** — Catches all private symbols, not just `_[A-Z]`

---

## Research Reference

All coders and reviewers MUST read before writing/reviewing:

1. **Test Desiderata (Kent Beck):** isolated, deterministic, fast, writable, readable, behavioral
2. **Functional Core / Imperative Shell:** Pure logic (test without mocks), I/O in shell (integration)
3. **Pytest Conventions:** Directory markers, fixture scoping, conftest hierarchy
4. **Injectable Seams:** Use FakeClock, FakeHeartbeat, FakeSpawnRepository — NO monkeypatching privates

Research: `.meridian/work/test-architecture-overhaul/requirements.md`
Fakes: `tests/support/fakes.py`

---

## Phase 0: Audit & Assign (1 coder)

Classify every test file AND assign lane:

| Classification | Lane | Action |
|----------------|------|--------|
| GOOD | — | Keep |
| MISCLASSIFIED | — | Move to correct dir |
| REWRITE | A-G | Archive + rewrite |
| DUPLICATE | — | Delete |

**Output:** `tests/_audit.md` — every REWRITE has lane assigned.

---

## Phase 1: Shared Infrastructure (Lane 0)

**Owner:** Single coder, STAYS AVAILABLE through Phase 2

**Scope:**
- `tests/support/fakes.py`
- `tests/support/fixtures.py`
- All `conftest.py` files

**Merge:** To main before other lanes branch.

**During Phase 2:** Lane 0 owner handles fake/fixture extensions requested by other lanes. Lanes rebase on Lane 0 updates before their own merge.

---

## Phase 2: Parallel Rewrite (Lanes A-E, G)

Each lane branches from main (post-Phase 1).

### Lane A: State & Persistence
- `spawn_store.py`, `session_store.py`, `work_store.py`
- `reaper.py`, `events.py`, `paths.py`, `liveness.py`

### Lane B: Streaming & Execution
- `streaming_runner.py`, `decision.py`, `errors.py`, `spawn_manager.py`

### Lane C: Process Launch
- `process/runner.py`, `pty_launcher.py`, `subprocess_launcher.py`, `session.py`

### Lane D: Harness Connections
- `harness/claude.py`, `harness/codex.py`, `harness/opencode.py`
- Workspace projection, connection lifecycle

### Lane E: CLI & Bootstrap
- `cli/bootstrap.py`, `primary_launch.py`, `main.py`

### Lane G: Catch-All
- `ops/`, `config/`, `catalog/`
- Anything else audit assigns

**Merge order:** Lanes can merge independently once reviewed + green + rebased on latest Lane 0.

---

## Phase 3: Contract Tests (Lane F) — AFTER A-E/G

Lane F starts AFTER interface-producing lanes (A-E, G) have merged.

### Lane F: Contract & Parity
- Verify contract tests against settled interfaces
- Add contracts for new seams
- Drift detection tests

**Merge:** After all interface lanes merged, Lane F is last code lane.

---

## Phase 4: Per-Lane Review

Each lane reviewer checks:
- [ ] No monkeypatching private internals
- [ ] Uses fakes where appropriate
- [ ] Behavior-named tests
- [ ] Correct unit/integration classification
- [ ] Archived tests' behaviors covered or explicitly dropped
- [ ] Rebased on Lane 0, branch green

---

## Phase 5: Integration & Platform Verification

1. All lanes merged to main
2. Full test suite green on Linux CI
3. **Full test suite green on Windows CI**
4. Platform tests (`tests/platform/`) verified on actual Windows
5. CI markers working (`pytest -m unit`, `pytest -m integration`)

---

## Phase 6: Stabilization

1. Keep `tests/_archived/` for 2 weeks after full green
2. Move to `docs/archived-tests/` as permanent reference
3. Document intentionally-not-replaced tests and reasoning

---

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Private monkeypatches in unit/ | 0 | `grep -rE "monkeypatch\.(setattr\|delattr).*['\"]_" tests/unit/` |
| Unit tests with tmp_path | 0 | `grep -r "tmp_path" tests/unit/` (should be 0) |
| Spawn lifecycle coverage | All transitions | Tests exist for: start→running, running→finalizing, finalizing→terminal, orphan detection |
| Reconciliation coverage | Reaper paths | Tests exist for: stale detection, fix-up, orphan marking |
| Process launch coverage | All launchers | Tests exist for: PTY launch, subprocess launch, artifact capture |
| Harness connect coverage | All states | Tests exist for: connect, interrupt, cancel, resume |
| Unit runtime (CI) | <30s | `time pytest -m unit` on CI |
| Full runtime (CI) | <90s | `time pytest` on CI |
| Linux CI | Green | GitHub Actions Linux job |
| **Windows CI** | **Green** | **GitHub Actions Windows job** |
| All lanes reviewed | ✓ | Review spawn succeeded |

---

## Execution Diagram

```
Phase 0 (audit)
    ↓
Phase 1 (Lane 0: shared infra) ──────────────────────┐
    ↓ merge to main                                  │
Phase 2 (parallel, rebasing on Lane 0)               │
    Lane A ─branch─→ rewrite ──┐                     │
    Lane B ─branch─→ rewrite ──┤                     │ Lane 0 owner
    Lane C ─branch─→ rewrite ──┼─→ review → merge    │ handles fake
    Lane D ─branch─→ rewrite ──┤    (rebase first)   │ extensions
    Lane E ─branch─→ rewrite ──┤                     │
    Lane G ─branch─→ rewrite ──┘                     │
    ↓ all interface lanes merged                     │
Phase 3 (Lane F: contracts) ─────────────────────────┘
    Lane F ─branch─→ contracts → review → merge
    ↓
Phase 5 (integration + Windows CI)
    ↓
Phase 6 (stabilization)
```

---

## For Impl-Orchestrator

When spawning coders, pass:
1. This plan (PLAN-V5.md)
2. Research: `.meridian/work/test-architecture-overhaul/requirements.md`
3. Audit: `tests/_audit.md`
4. Archived tests: `tests/_archived/<lane>/`
5. Fakes: `tests/support/fakes.py`

**Lane 0 coder** stays available through Phase 2 to handle shared infra updates.
**Lane F coder** waits until A-E/G are merged.

Each coder READS research on Test Desiderata and functional core BEFORE writing.
