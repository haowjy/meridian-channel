# Agent Staffing — Config Layer Unification

## Round 1 (Parallel — 3 coders)

### Phase 1: Audit & Drift Test
- **Implementer**: `coder` (straightforward test authoring, no ambiguity)
- **Model**: default (test writing is mechanical)
- **Context files**: `01-audit-drift-test.md`, `settings.py`, `agent.py`, `models.py`, `spawn.py`, `main.py`, `launch/types.py`
- **Verification**: `verification-tester`

### Phase 2: Rename autocompact_pct
- **Implementer**: `coder`
- **Model**: default
- **Context files**: `02-rename-autocompact.md`, `settings.py`
- **Verification**: `verification-tester`

### Phase 3.1: Config Layer Expansion
- **Implementer**: `coder`
- **Model**: default
- **Context files**: `03-1-config-layer-expansion.md`, `settings.py`, `agent.py` (for known value sets)
- **Verification**: `verification-tester`

## Round 2

### Phase 3.2: Primary CLI Expansion
- **Implementer**: `coder`
- **Model**: default (pattern matching against existing spawn CLI)
- **Context files**: `03-2-primary-cli-expansion.md`, `main.py`, `launch/types.py`, `spawn.py` (as pattern reference)
- **Verification**: `verification-tester`, `smoke-tester` (test `--dry-run` with new flags)

## Round 3

### Phase 3.3: Runtime Wiring
- **Implementer**: `coder`
- **Model**: stronger reasoning recommended — this phase has the most architectural judgment calls (precedence chain, interaction between config/profile/CLI layers)
- **Context files**: `03-3-runtime-wiring.md`, `launch/plan.py`, `prepare.py`, `launch/resolve.py`, `settings.py`, `permissions.py`
- **Reviewers**:
  - Focus: correctness of precedence chain (`reviewer` — "verify that the resolution order CLI > Profile > Config is consistently applied across all fields in both primary and spawn paths")
  - Focus: design alignment (`reviewer` — "verify changes match the config-layer-unification design spec")
- **Verification**: `verification-tester`, `smoke-tester`

## Round 4

### Phase 4: Naming Convention Enforcement
- **Implementer**: `coder`
- **Model**: default
- **Context files**: `04-naming-convention-enforcement.md`, `tests/test_config_layer_consistency.py` (from Phase 1)
- **Verification**: `verification-tester`

## Post-Completion

- **Documenter**: Mine conversation for decisions about precedence ordering, naming exceptions, and deprecated alias handling. Update tech docs.
- **Investigator** (background): Sweep for any deferred items (e.g., harness adapter changes needed for budget/max_turns passthrough).

## Parallelism Summary

```
Round 1: Phase 1 ║ Phase 2 ║ Phase 3.1    (3 parallel coders)
Round 2: Phase 3.2                         (1 coder, needs 3.1)
Round 3: Phase 3.3                         (1 coder + 2 reviewers, needs 3.2 + 2)
Round 4: Phase 4                           (1 coder, needs all)
```

Total: 6 coder sessions, 2 reviewer sessions, 4+ verification sessions.
Critical path: 4 rounds.
