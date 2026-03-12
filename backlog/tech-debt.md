# Tech Debt

Code and test cleanup. Last verified: 2026-03-11.

## Open

| ID | Summary | Priority | Why it exists now | Desired endpoint |
|----|---------|----------|-------------------|------------------|
| TD-18 | Unify launch lifecycle across primary, foreground child, and background child | High | Launches now share the same durable-PID-first intent, but the transition logic is still split across `launch/process.py`, `launch/runner.py`, and `ops/spawn/execute.py`. That keeps lifecycle rules coherent only by convention. | One shared launch lifecycle module owns `queued -> running -> terminal`, PID persistence, and launch-mode semantics for every run type. |
| TD-19 | Split `spawn/execute.py` by responsibility | High | `src/meridian/lib/ops/spawn/execute.py` is still carrying spawn initialization, session/materialization setup, background launcher construction, worker re-entry, and blocking execution flow in one file. | Separate modules for spawn initialization/state writes, session/materialization context, background launcher plumbing, and blocking/background execution entrypoints. |
| TD-20 | Separate runtime inspection from reconciliation policy in `state/reaper.py` | Medium | The reaper is cleaner after the ghost-spawn refactor, but it still combines “inspect disk/process reality” and “decide repair action” in the same module path. | A typed runtime snapshot plus a typed reconciliation decision model, so inspection can be tested independently from policy. |
| TD-21 | Move runner artifact handling to explicit streaming sinks | Medium | `launch/stream_capture.py` now isolates framing, but `launch/runner.py` still does post-run artifact mirroring and mixes process lifecycle with sink orchestration. | Explicit stream sinks for log-file persistence, artifact persistence, token extraction, and event parsing, with the runner coordinating them instead of owning their mechanics. |
| TD-22 | Tighten spawn event/state typing for lifecycle phases and failure categories | Medium | Launch mode and active-status typing improved, but several fields still rely on free-form strings and implicit conventions that make future lifecycle work easier to regress. | Stronger typed lifecycle/failure categories across state/event models so invalid transitions and ambiguous repair reasons are harder to encode. |

## Archived (2026-03-05 harness cleanup batch)

| ID | Summary | Status | Resolution Commit(s) |
|----|---------|--------|----------------------|
| TD-9 | Finish space-plumbing follow-up cleanup (report-path semantics, artifact scoping) | Closed | Flat `.meridian/` layout completed; old space-specific follow-up retired |
| TD-17 | Extract per-harness prompt/resume policy from shared launch assembly | Closed | Harness cleanup Step 1: adapter launch hooks (seed_session, filter_launch_content, detect_primary_session_id) |

## Archived (2026-03-04 cleanup batch)

| ID | Summary | Status | Resolution Commit(s) |
|----|---------|--------|----------------------|
| TD-7 | Deduplicate launch resolution/assembly across `launch.py` and spawn prepare path | Closed | `bda59aa` |
| TD-10 | Align bundled skill content strategy (naming, materialization, skill content) | Closed | `b1d859d`, `77cffef`, `d434984`, `a7ccecf` |
| TD-11 | Validate/polish Claude native-agent passthrough edge cases and doc/code alignment | Closed | `e444f60`, `9f39e24`, `a28143b` |
| TD-12 | Remove harness-id string branching for reference loading mode | Closed | `87af9f0` |
| TD-13 | Remove Claude-specific allowed-tools merge from generic strategy builder | Closed | `87af9f0` |
| TD-14 | Unify primary launch env wiring with adapter env/MCP env flow | Closed | `bda59aa` |
| TD-15 | Replace hardcoded primary harness override allowlist with registry-derived validation | Closed | `87af9f0` |
| TD-16 | Replace `_build_interactive_command` with adapter-delegated command building | Closed | `bda59aa` |

## Archived (2026-03-03 backlog execution batch)

| ID | Summary | Status | Resolution Commit(s) |
|----|---------|--------|----------------------|
| TD-8 | Complete primary CLI redesign (`meridian` root entry + real `--continue`) | Closed | `ec5f806`, `76d9678`, `248b97d`, `2950a8b`, `f533a23` |
| TD-1 | Unify spawn execution lifecycle paths | Closed | `deaee4c` |
| TD-2 | Consolidate space resolution and `@name` loading | Closed | `aeb01c9` |
| TD-3 | Merge warning/normalization utilities | Closed | `ae61da7` |
| TD-4 | Consolidate CLI spawn plumbing tests | Closed | `8b33a8a` |
| TD-5 | Remove overlapping streaming tests | Closed | `88a3429` |
| TD-6 | Centralize subprocess test helpers | Closed | `6d6fcf0` |

## Archive Reference

- Full batch archive: `backlog/archive/2026-03-03-backlog-execution.md`
- Follow-up notes from deleted plan docs: `backlog/plan-cleanup-notes.md`
