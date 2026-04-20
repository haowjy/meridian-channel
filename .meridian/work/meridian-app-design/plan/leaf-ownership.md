# Leaf Ownership

| Contract ID | Summary | Owner phase | Status | Tester lane | Evidence pointer | Revised |
|---|---|---|---|---|---|---|
| `APP-SESS-01` | `GET /api/spawns` supports opaque cursors and Sessions-mode filters | Phase 1 | planned | `@integration-tester` | `plan/phase-1-sessions-sse-work.md` | no |
| `APP-SESS-02` | `GET /api/spawns/stats` returns dashboard counters | Phase 1 | planned | `@integration-tester` | `plan/phase-1-sessions-sse-work.md` | no |
| `APP-SESS-03` | `GET /api/stream` emits multiplexed SSE updates | Phase 1 | planned | `@integration-tester`, `@smoke-tester` | `plan/phase-1-sessions-sse-work.md` | no |
| `APP-SESS-04` | `GET /api/spawns/{spawn_id}/events` exposes per-spawn event history/tail | Phase 1 | planned | `@integration-tester` | `plan/phase-1-sessions-sse-work.md` | no |
| `APP-WORK-01` | `/api/work` list/detail/create/archive facade | Phase 1 | planned | `@integration-tester` | `plan/phase-1-sessions-sse-work.md` | no |
| `APP-WORK-02` | `/api/work/active` read/write active work selection | Phase 1 | planned | `@integration-tester` | `plan/phase-1-sessions-sse-work.md` | no |
| `APP-WORK-03` | `/api/work/{work_id}/sync` trigger/poll contract | Phase 1 | planned-external-dependency | `@integration-tester`, `@smoke-tester` | `plan/phase-1-sessions-sse-work.md` | no |
| `APP-SPAWN-01` | `POST /api/spawns/{spawn_id}/fork` forks from existing session context | Phase 2 | planned | `@integration-tester` | `plan/phase-2-files-and-spawn-lifecycle.md` | no |
| `APP-SPAWN-02` | `POST /api/spawns/{spawn_id}/archive` durably hides terminal spawns from default lists | Phase 2 | planned | `@integration-tester` | `plan/phase-2-files-and-spawn-lifecycle.md` | no |
| `APP-FILES-01` | `GET /api/files/tree` lists project-root-relative entries | Phase 2 | planned | `@integration-tester` | `plan/phase-2-files-and-spawn-lifecycle.md` | no |
| `APP-FILES-02` | `GET /api/files/read` returns safe file content reads | Phase 2 | planned | `@integration-tester` | `plan/phase-2-files-and-spawn-lifecycle.md` | no |
| `APP-FILES-03` | `GET /api/files/diff` returns project-scoped diffs | Phase 2 | planned | `@integration-tester`, `@smoke-tester` | `plan/phase-2-files-and-spawn-lifecycle.md` | no |
| `APP-FILES-04` | `GET /api/files/meta` returns file metadata and related context | Phase 2 | planned | `@integration-tester` | `plan/phase-2-files-and-spawn-lifecycle.md` | no |
| `APP-FILES-05` | `GET /api/files/search` searches within the bound project only | Phase 2 | planned | `@integration-tester` | `plan/phase-2-files-and-spawn-lifecycle.md` | no |
| `APP-CAT-01` | `GET /api/agents` exposes available agent profiles | Phase 3 | planned | `@integration-tester` | `plan/phase-3-inspector-and-catalog.md` | no |
| `APP-CAT-02` | `GET /api/models` exposes model catalog and routing hints | Phase 3 | planned | `@integration-tester` | `plan/phase-3-inspector-and-catalog.md` | no |
| `APP-THREAD-01` | `GET /api/threads/{chat_id}/events/{event_id}` returns persisted raw event data | Phase 3 | planned | `@integration-tester` | `plan/phase-3-inspector-and-catalog.md` | no |
| `APP-THREAD-02` | `GET /api/threads/{chat_id}/tool-calls/{call_id}` returns persisted tool-call detail | Phase 3 | planned | `@integration-tester` | `plan/phase-3-inspector-and-catalog.md` | no |
| `APP-THREAD-03` | `GET /api/threads/{chat_id}/token-usage` returns token/cost projection | Phase 3 | planned | `@integration-tester` | `plan/phase-3-inspector-and-catalog.md` | no |
