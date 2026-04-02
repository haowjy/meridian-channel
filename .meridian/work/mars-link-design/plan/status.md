# Implementation Status

## Execution Order

```
Phase 1: Error model & constants                (foundation)
  ↓
Phase 2: MarsContext struct & command migration   (foundation)
  ↓
Phase 3: ConfigMutation extension & mutate_config (parallel with 6)
Phase 6: Doctor link validation                   (parallel with 3)
  ↓
Phase 4: Link command redesign                    (requires 1, 2, 3)
  ↓
Phase 5: Init redesign                            (requires 2, 4)
```

## Dependency Graph

```
Round 1: Phase 1
Round 2: Phase 2
Round 3: Phase 3, Phase 6  (independent — both need Phase 2)
Round 4: Phase 4            (needs Phase 3)
Round 5: Phase 5            (needs Phase 4)
```

## Phase Status

| Phase | Status | Notes |
|---|---|---|
| 1. Error model & constants | not started | |
| 2. MarsContext & migration | not started | |
| 3. ConfigMutation extension | not started | |
| 4. Link redesign | not started | Core feature, highest risk |
| 5. Init redesign | not started | |
| 6. Doctor link checks | not started | |
