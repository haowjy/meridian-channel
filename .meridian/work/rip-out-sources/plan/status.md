# Implementation Status

| Phase | Description | Status | Notes |
|-------|-------------|--------|-------|
| 1 | Atomic removal — install module, callers, CLI, tests | pending | Sequential: must go first |
| 2a | Clean state paths and gitignore | pending | Sequential: after Phase 1 |
| 2b | Remove provenance/bootstrap schema fields (~12 files) | pending | Sequential: after Phase 2a |
| 3 | Update ALL docs (README, INSTALL, AGENTS, config, smoke tests) | pending | Parallel with Phase 4 |
| 4 | Improve error UX — missing agent/skill messages, doctor, pyproject.toml dep | pending | Parallel with Phase 3 |
