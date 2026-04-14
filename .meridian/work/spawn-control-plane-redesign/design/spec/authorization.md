# Authorization — Lifecycle Operations Are Gated

Cancel and interrupt are **lifecycle and turn-control** operations. An
arbitrary subagent should not terminate sibling spawns or wedge an
unrelated user's spawn. The model is **capability-by-ancestry**: a process
may operate on the spawn it owns or its descendants. Inject (cooperative
text) is **not** gated.

## Threat model

- A spawned subagent (`MERIDIAN_SPAWN_ID=<my_id>`) shells out
  `meridian spawn cancel <other_id>`. If `<other_id>` is not in the
  agent's ancestry, deny.
- A spawned subagent issues `POST /api/spawns/<other_id>/cancel` against
  the AF_UNIX app server. Same rule; caller identified via `SO_PEERCRED`.
- Local human runs `meridian spawn cancel <id>` from an interactive shell
  with no `MERIDIAN_SPAWN_ID` and `MERIDIAN_DEPTH=0`. Trusted operator;
  always allowed.
- A subagent at `MERIDIAN_DEPTH > 0` with `MERIDIAN_SPAWN_ID` missing
  (env-drop bug). Denied by default (D-14). NOT treated as operator.
- A child agent connects, the server gets its PID via SO_PEERCRED, but
  the child exits before `/proc/<pid>/environ` can be read. Identity
  extraction fails. Denied by default (D-19).
- Remote attacker reaching the app server. Out of scope — AF_UNIX is
  filesystem-permissioned; no network exposure (D-11, resolves BL-6).

## EARS Statements

### AUTH-001 — Cancel and interrupt require ancestry authorization

**When** any caller invokes a lifecycle operation (cancel, interrupt) for
`<target>` and the caller has `MERIDIAN_SPAWN_ID=<caller>`,
**the surface shall** authorize only when `<caller> == <target>` or
`<caller>` is an ancestor of `<target>` per the `parent_id` chain.

**Observable.** Authorization logged with `reason in {"ancestor", "self"}`
on accept; `reason in {"not_in_ancestry", "missing_target"}` on deny.

### AUTH-002 — Operator surface at depth 0

**When** a caller has `MERIDIAN_SPAWN_ID` unset **and**
`MERIDIAN_DEPTH == 0` (or unset),
**the surface shall** treat the caller as operator and allow the operation.

**Observable.** `meridian spawn cancel <id>` from a human shell works.
Logs record `auth_mode="operator"`.

### AUTH-003 — Denials surface a clear error

**When** authorization denies a lifecycle operation,
**the surface shall** respond with transport-appropriate error:

| Surface | Response |
|---|---|
| CLI | exit 2; stderr `Error: caller <caller> is not authorized to <action> <target>` |
| HTTP | `403 Forbidden` with `{"detail": "caller is not authorized"}` |
| Control socket | `{"ok": false, "error": "interrupt requires caller authorization"}` |

**Observable.** No SIGTERM, no finalize events, no `inbound.jsonl` entry.

### AUTH-004 — Authorization at surface, not in SpawnManager

**When** the lifecycle pipeline executes,
**the auth check shall** happen at the surface **before** any side-effect.

**Observable.** `SpawnManager` and `SignalCanceller` are unaware of
authorization.

### AUTH-005 — Ancestry walk is bounded

**When** the guard walks the `parent_id` chain,
**the walk shall** stop at first match, `parent_id is None`, or
`_AUTH_ANCESTRY_MAX_DEPTH` (32) hops.

**Observable.** Read-only, bounded. Cycles terminate within depth bound.

### AUTH-006 — Agent-tool surface defers to the same guard

**When** agent runtime exposes cancel/interrupt as tools,
**the runtime shall** invoke CLI/Python entrypoint without bypassing
`AuthorizationGuard`.

**Observable.** No agent-side auth codepath. Profile allowlist controls
tool availability; guard controls authorization.

### AUTH-007 — Depth > 0 with missing caller is deny-by-default (v2 new)

**When** `MERIDIAN_DEPTH > 0` (inside a spawn) and `MERIDIAN_SPAWN_ID`
is unset or empty,
**the surface shall** deny with reason `"missing_caller_in_spawn"`.

An explicit `--operator-override` CLI flag bypasses this for debugging.

**Observable.** A subagent whose env drops `MERIDIAN_SPAWN_ID` cannot
cancel/interrupt any spawn. Logs record `auth_mode="missing_caller_in_spawn"`.

**Why (v2).** v1 treated missing env as operator regardless of depth. This
is fail-open inside spawn trees — env-drop bugs auto-promote subagents.
D-14 closes the gap.

## Verification plan

### Unit tests
- `authorize()` for: caller=None depth=0 (operator), caller=None depth>0
  (deny), caller=self, caller=parent, caller=grandparent, caller=sibling
  (deny), caller=stranger (deny), target=missing (deny), cycle in chain.
- `caller_from_env()` handles unset, empty, padded strings.

### Smoke tests
- Scenario 16: child cancels itself → allowed. Child cancels sibling →
  403 / exit 2.
- Scenario 17: operator shell cancels any spawn → allowed.
- Scenario 18: control-socket interrupt from non-ancestor → rejected.

### Fault-injection tests
- **Env-drop**: spawn at depth > 0 with `MERIDIAN_SPAWN_ID` cleared;
  verify cancel denied, not treated as operator.
- **Deep ancestry**: chain of 30+ nested spawns; verify ancestry walk
  reaches the root and authorizes correctly.
