# Test Architecture Overhaul — Plan v3

**Revision:** Archive old → parallel rewrite by module → review each lane

---

## Key Changes from v2

1. **Archive, don't delete** — Move to `tests/_archived/` as reference, not destruction
2. **Audit-informed archival** — Know what we're archiving and why
3. **Parallel rewrite lanes** — Multiple coders working on different modules simultaneously
4. **Per-lane review** — Each module gets reviewed before merge
5. **Realistic success criteria** — Coverage-based, not count-based

---

## Current State (post-refactoring)

| Directory | Test Count | Status |
|-----------|------------|--------|
| tests/unit/ | ~87 | Mixed quality — some good pure tests, some monkeypatch-heavy |
| tests/integration/ | ~459 | Mostly good, some misclassified |
| tests/contract/ | ~82 | Parity/drift tests |
| tests/platform/ | ~13 | Windows/Unix specific |
| tests/support/ | 0 | Fakes and fixtures (not tests) |

**Problems:**
- 17 monkeypatches in unit tests (should be 0)
- Unit tests not using new fakes (FakeClock, etc.)
- Some "unit" tests have filesystem access (should be integration)
- Harness tests especially brittle (test_lifecycle.py, test_codex_ws.py)

---

## Phase 0: Audit & Classify (1 coder)

Before archiving, classify every test file:

| Classification | Action |
|----------------|--------|
| **GOOD** | Keep in place, no rewrite needed |
| **MISCLASSIFIED** | Move to correct directory (unit→integration or vice versa) |
| **REWRITE** | Archive, needs fresh rewrite using new seams |
| **DUPLICATE** | Delete outright |

Output: `tests/_audit.md` with per-file classification and reasoning.

---

## Phase 1: Archive (1 coder)

Move all REWRITE-classified tests to `tests/_archived/`, preserving directory structure:

```
tests/_archived/
├── unit/
│   ├── harness/          # Most monkeypatch-heavy
│   │   ├── test_lifecycle.py
│   │   └── test_codex_ws.py
│   └── ...
└── integration/
    └── ...
```

After this phase: test suite may be broken or thin. That's expected.

---

## Phase 2: Parallel Rewrite (4-6 coders)

Each coder owns one lane, writes fresh tests using new seams:

### Lane A: State & Persistence
- `spawn_store.py` — using FakeSpawnRepository, FakeClock
- `reaper.py` — reconciliation logic
- `events.py` — pure function (already good, verify)

### Lane B: Streaming & Execution  
- `streaming_runner.py` — using FakeHeartbeat, FakeClock
- `decision.py` — pure function (already good, verify)
- `errors.py` — retry classification

### Lane C: Process Launch
- `process/runner.py` — launcher selection
- `process/pty_launcher.py` — PTY-specific (platform)
- `process/subprocess_launcher.py` — subprocess capture

### Lane D: Harness Connections
- `harness/claude.py` — connection lifecycle
- `harness/codex.py` — websocket handling
- `harness/opencode.py` — if applicable
- Workspace projection tests

### Lane E: CLI & Bootstrap
- `cli/bootstrap.py` — command dispatch
- `cli/primary_launch.py` — launch policy
- `cli/main.py` — integration paths

### Lane F: Contract Tests
- Verify contract tests still valid
- Update any that reference archived code
- Add contracts for new seams

---

## Phase 3: Per-Lane Review (parallel reviewers)

Each lane gets a dedicated reviewer checking:
- No monkeypatching of private internals
- Proper use of fakes where applicable
- Pure functions tested without fakes (don't force fakes)
- Behavior-named tests
- Correct classification (unit vs integration)

Reviewer can request changes before lane merges.

---

## Phase 4: Integration & Cleanup

1. Run full test suite — should pass
2. Verify coverage on critical paths
3. Delete `tests/_archived/` (or keep as reference)
4. Update CI markers if needed

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Monkeypatches of private internals in unit/ | 0 |
| Unit tests using tmp_path/filesystem | 0 (move to integration) |
| Critical path coverage | spawn lifecycle, reconciliation, process launch, harness connect |
| Test runtime (unit marker) | <30s |
| Test runtime (full suite) | <60s |
| All lanes reviewed | ✓ |

**Not measuring:** Total test count. Quality over quantity.

---

## Execution Order

```
Phase 0 (audit)
    ↓
Phase 1 (archive)
    ↓
Phase 2 (parallel rewrite)
    Lane A ──→ Review A ──┐
    Lane B ──→ Review B ──┤
    Lane C ──→ Review C ──┼──→ Phase 4 (integrate)
    Lane D ──→ Review D ──┤
    Lane E ──→ Review E ──┤
    Lane F ──→ Review F ──┘
```

---

## Reference

Archived tests in `tests/_archived/` serve as:
- Expected behavior reference
- Edge case discovery
- "What did this test?" documentation

Coders should read archived tests before writing replacements.
