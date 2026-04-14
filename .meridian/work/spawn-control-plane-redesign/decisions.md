# Design Decisions — Spawn Control Plane (v2)

Append-only log of the non-obvious judgment calls made during this design
cycle. v1 decisions preserved where noted; v2 revisions flagged.

## D-01 — Cancel goes through OS signals, not control-socket transitions

**v1 decision preserved.** All cancel callers funnel through
`SignalCanceller.cancel(spawn_id)` → SIGTERM to the runner PID. Runner's
existing SIGTERM handler drives `manager.stop_spawn(status="cancelled",
origin="runner")`.

**v2 change:** app-managed spawns now also go through SIGTERM because the
app server moves to AF_UNIX per D-11, giving each app-managed spawn an
addressable runner process (the FastAPI worker). See D-11 for the
unification argument.

## D-02 — Heartbeat ownership moves to SpawnManager (LIV-003)

**v1 decision preserved.** Extract `heartbeat_loop` helper; SpawnManager
starts/stops it per spawn. Runners delegate to the helper.

## D-03 — Two-lane cancel: SIGTERM for CLI, in-process for app (v2 revised)

**v1 chose:** claimed one pipeline but had two hidden behind one name.

**v2 initial attempt:** cancel-target coordination file + shared worker
SIGTERM. Reviewers (p1794, p1795) blocked: external SIGTERM (timeout
supervisors, OOM killers) to the shared worker PID cannot target a
specific spawn because no cancel-target file exists in that path. The
cancel-target file is a side-channel that only `SignalCanceller` writes.

**v2 final choice:** explicitly adopt two-lane cancel (BL-1 option b).
Document why they cannot converge:

- **CLI-launched spawns** (one runner process per spawn): cancel via
  SIGTERM to `runner_pid`. Runner's signal handler calls
  `manager.stop_spawn(status="cancelled")`. This is the existing path.
- **App-managed spawns** (shared FastAPI worker): cancel via
  `SignalCanceller.cancel()` which detects `launch_mode == "app"` and
  calls `manager.stop_spawn()` in-process (or routes through HTTP
  `POST /cancel` when invoked from a different process). No SIGTERM to
  the shared worker.

**Why unification is not feasible.** The fundamental constraint:
SIGTERM is a process-level signal with no per-spawn addressing. A shared
FastAPI worker hosts multiple spawns; SIGTERM-ing it kills all of them
(or requires a coordination file side-channel that external supervisors
don't write). Per-spawn worker processes would solve this but are a
much larger architectural change (process pool, affinity routing, etc.)
that is out of scope for this issue set.

**What IS unified.** The `SignalCanceller` class is the single entry
point for all cancel callers. The dispatcher logic inside SignalCanceller
branches on `launch_mode`:
- `launch_mode in ("foreground", "background")`: SIGTERM to `runner_pid`.
- `launch_mode == "app"`: in-process `manager.stop_spawn()` or HTTP
  `POST /cancel` (if cross-process).

Both branches converge on the same terminal state: `status="cancelled"`,
`origin="runner"` (preferred) or `origin="cancel"` (fallback).

**Tradeoff.** External timeout supervisors cannot cancel individual app-
managed spawns via SIGTERM. They can only kill the worker (all spawns
die). This is acceptable: app-managed spawns are managed by the app
server, and the app server has its own cancel endpoint. External
supervisors are CLI-launcher concerns.

**What this means for the success criterion.** "Cancel semantics are
consistent across CLI, HTTP, and timeout kill" is satisfied for CLI
spawns. For app spawns, CLI cancel and HTTP cancel converge; timeout kill
affects the whole worker (documented, not a bug).

## D-04 — `turn/completed` never spawn-terminal (INT-002)

**v1 decision preserved.** Per-turn payloads don't finalize the spawn.
`_terminal_event_outcome` returns `None` for `turn/completed` regardless
of `turn.status`.

## D-05 — Per-spawn asyncio.Lock for inject/interrupt serialization (INJ-002)

**v1 decision preserved.** `inject_lock` module with
`dict[SpawnId, asyncio.Lock]`. SpawnManager.inject and .interrupt acquire
the lock.

**v2 extension (per BL-1 major).** Lock scope now includes the ack/reply
emission, not just `record_inbound + send_*`. The control socket writes
its JSON reply inside the lock, so ack arrival order matches `inbound.jsonl`
order. See architecture `inject_serialization.md` for the extended scope.

## D-06 — Authorization by env-derived caller id, not tokens (revised transport)

**v1 decision revised.** The core `authorize()` function is unchanged (pure
function over `state_root, target, caller`). The transport for HTTP caller
identification changes:

**v1 proposed:** TCP loopback + `SO_PEERCRED` to read peer PID + read
`/proc/<pid>/environ`. Reviewers flagged this as non-portable (BL-3).

**v2 choice:** AF_UNIX socket for the app server (D-11). `SO_PEERCRED`
on AF_UNIX reliably provides peer PID on Linux. On macOS,
`LOCAL_PEERCRED` / `getpeereid()` provides uid/gid but not PID.

**v2r2 revision (post-review).** Reviewers (p1794, p1795) flagged the
macOS operator fallback as fail-open. v2r2 fixes:
- Identity extraction failure on HTTP/socket surfaces → **DENY**, not
  operator. Reason: `"peercred_unavailable"`.
- Operator mode is only available via CLI env path (`MERIDIAN_DEPTH == 0`,
  `MERIDIAN_SPAWN_ID` unset, checked in the process's own environment).
- This redesign does **not** define an HTTP/header fallback for
  peercred-unavailable platforms. Supporting them would require a
  different caller-identity transport, which is out of scope here.

**Alternative rejected (v2).** Per-spawn/per-session tokens. Would add
token rotation, storage, and revocation surfaces. The threat model (honest
actors) doesn't justify the complexity.

## D-07 — Inject stays un-gated

**v1 decision preserved.** Inject is cooperative data-plane; no
authorization gate.

## D-08 — Delete `SpawnManager.cancel` outright; no shim (R-06)

**v1 decision preserved.** Remove the method, its control-socket handler,
and the CLI `--cancel` flag in the same change set.

## D-09 — Rejected: cancel via "terminal message" over control socket

**v1 decision preserved.** No `type="cancel_graceful"` on the control
socket.

## D-10 — App-launched spawns populate `runner_pid` with FastAPI worker PID

**v1 decision preserved.** `runner_pid=os.getpid()` at spawn creation
in the FastAPI worker.

## D-11 — App server moves to AF_UNIX socket (v2 new)

**Choice.** The app server binds to an AF_UNIX socket
(`.meridian/app.sock`) instead of TCP `127.0.0.1:8420`. Uvicorn supports
`--uds` natively. The frontend connects via the Unix socket (browsers
cannot; the frontend dev server proxies).

**Why this resolves BL-3 + BL-6 together.**
- BL-3 (HTTP caller identity): AF_UNIX provides `SO_PEERCRED` for peer
  PID. No need for TCP loopback peercred hacks.
- BL-6 (loopback not enforced): AF_UNIX sockets are filesystem objects
  with standard Unix permissions. No `--host 0.0.0.0` exposure risk.
  The `--host` flag is removed; replaced by `--uds <path>`.

**Tradeoff.** Browser-based development needs a proxy. The app ships a
tiny `--proxy` mode that binds TCP `127.0.0.1:<port>` and forwards to
the Unix socket. Production GUI usage goes through the proxy; CLI and
agent callers connect to the socket directly.

**Alternatives rejected.**
1. *Keep TCP, add token auth.* Adds a token lifecycle surface
   (generation, rotation, distribution to spawns). Overcomplicated for
   an honest-actors model.
2. *Keep TCP, enforce `--host 127.0.0.1` in code.* Fixes BL-6 but not
   BL-3 (TCP loopback still has no reliable peer-PID).

## D-12 — `launch_mode` gains `"app"` value (v2 new, resolves BL-2)

**Choice.** Extend `LaunchMode = Literal["background", "foreground", "app"]`.
App server sets `launch_mode="app"` at spawn creation. This is the durable
owner discriminator that the cancel dispatcher, reaper, and status
display use to distinguish app-managed spawns.

**Why `"app"` not a separate field.** The existing `launch_mode` field
already answers "who launched this spawn". Adding a separate `owner`
field is redundant — `launch_mode` IS the ownership signal. A new value
in the existing enum is simpler than a new column.

**Note on cancel dispatch.** With D-03 (two-lane cancel), the
`launch_mode` field is the dispatch key: `SignalCanceller` branches on
`launch_mode == "app"` to choose in-process vs SIGTERM cancel.

## D-13 — No SIGKILL escalation at all; SIGTERM + wait + reaper (v2r2, resolves BL-4)

**v2 initial attempt:** re-check `finalizing` before SIGKILL. Reviewer
(p1795) flagged: the spawn can enter `mark_finalizing` in the window
between the re-check and `os.kill(SIGKILL)`. This TOCTOU race is
inherent to the design because the runner and canceller are in different
processes with no shared lock.

**v2r2 choice.** Remove SIGKILL escalation entirely from `SignalCanceller`.
The cancel pipeline is: SIGTERM → wait for terminal row → if grace expires,
return 503 and let the reaper handle it. No SIGKILL ever.

**Why no SIGKILL.** The TOCTOU race between "is this process finalizing"
and "kill it" cannot be closed without a cross-process lock, which is
more mechanism than the problem warrants. The reaper already handles
stuck processes (stale heartbeat → reconciliation). SIGKILL was a
convenience optimization for "runner is hung"; removing it simplifies
the pipeline and eliminates the race at no operational cost — the reaper
converges on the same outcome within `heartbeat_window`.

**What CAN-003 becomes.** Grace expiry returns 503 (HTTP) or prints
"spawn did not terminate within grace; reaper will reconcile" (CLI).
There is no separate `forced` flag in `CancelOutcome` because the cancel
pipeline never force-kills. If the runner IS hung (not finalizing, just
stuck), the reaper detects
stale heartbeat + dead process and writes `origin="reconciler"`.

**Tradeoff.** A hung runner takes up to `heartbeat_window` (120s) to be
reaped instead of `cancel_grace_seconds` (5s). This is acceptable:
hung runners are already rare, and the reaper is the designed safety net.

## D-14 — `depth > 0 ∧ caller_id missing` is deny-by-default (v2 new)

**Choice.** When `MERIDIAN_DEPTH > 0` (inside a spawn) and
`MERIDIAN_SPAWN_ID` is unset or empty, `authorize()` returns DENY with
reason `"missing_caller_in_spawn"`. An explicit `--operator-override` CLI
flag bypasses this for debugging.

**Why.** The v1 design treated missing env as "trusted operator" in all
cases. Reviewers correctly flagged this as fail-open inside spawn trees —
env-drop bugs would auto-promote subagents to operator status. The fix:
operator status is only implicit at `depth == 0` (interactive shell).

## D-15 — PID-reuse guard in SignalCanceller (v2 new)

**Choice.** `SignalCanceller._resolve_runner_pid` passes
`created_after_epoch=_epoch_from_started_at(record.started_at)` to
`is_process_alive`, matching the reaper's guard in `reaper.py:127-129`.
`SpawnRecord` already stores `started_at` as ISO 8601, so the guard
converts that field at use time rather than adding a second persisted
timestamp. If the PID has been reused, the resolver returns `None` and
falls through to the finalize-only path (no SIGTERM sent to a stranger
process).

## D-16 — Terminal-cancel HTTP returns 409 (v2 new, resolves BL-7)

**Choice.** Spec and architecture agree: cancel against an already-terminal
spawn returns `409 Conflict` with FastAPI's standard
`{"detail": "spawn already terminal: <status>"}` envelope. The v1
architecture sketch that said `200 with already_terminal=true` is removed.

**Why 409 over 200.** The client asked for a state transition that cannot
happen. 409 is semantically correct for "conflict with current resource
state". Returning 200 would force every client to check a boolean flag
to know whether the cancel actually did anything.

## D-17 — Semantic validation → 400, schema validation → 422 (v2r2 new)

**Choice.** Split HTTP validation errors into two tiers:
- **422**: FastAPI/pydantic structural validation (missing fields, wrong
  types). Handled by FastAPI's default exception handler.
- **400**: Semantic validation (text + interrupt both set, text empty and
  interrupt false). Handled by a custom exception handler that catches
  `ValueError` from `model_validator` and remaps to 400.

This resolves the p1794 finding that INT-006 says 400 but pydantic
`model_validator` produces 422 by default.

## D-18 — INJ-002 contract narrowed to `inbound_seq` ordering (v2r2 new)

**Choice.** The INJ-002 contract specifies that concurrent injects are
linearized in `inbound.jsonl` order and harness delivery order. Ack
arrival order at clients is **not** guaranteed to match for HTTP clients
(separate TCP/Unix connections with independent response timing).

For control socket clients, ack ordering IS guaranteed by the `on_result`
callback (D-05 extension). For HTTP clients, `inbound_seq` in the
response is sufficient for clients to reconstruct ordering.

This resolves the p1795 major about HTTP ack ordering.

## D-19 — Peercred failure → DENY for lifecycle ops (v2r2 new)

**Choice.** When `SO_PEERCRED` fails or `/proc/<pid>/environ` is
unreadable (peer exited, macOS, permission denied), the auth surface
returns DENY for lifecycle operations, not operator fallback.

CLI env path remains the only operator path. HTTP/socket callers whose
identity cannot be determined are denied by default.

This resolves both the p1794 blocker (macOS operator fallback) and the
p1795 blocker (peer-exit race). The fallback from a failed peercred
read is the same as "missing caller at depth > 0": deny.

## D-20 — Timeout-kill consistency scoped to CLI spawns (v2r2 new)

**Choice.** The requirements success criterion "cancel semantics are
consistent across CLI, HTTP, and timeout kill" is satisfied for CLI
spawns. For app spawns, CLI cancel and HTTP cancel converge on the same
terminal state; timeout kill affects the entire FastAPI worker (all
hosted spawns die), which is documented behavior, not a bug.

This is a direct consequence of D-03 (two-lane cancel). External
timeout supervisors issue SIGTERM to processes, which has no per-spawn
addressing in a shared worker. The app server has its own cancel
endpoint for targeted cancel.

## Cleanup appendix (v2r2 narrow cleanup)

### D-21 — Terminal cancel uses the shared FastAPI error envelope

**Choice.** Already-terminal `POST /cancel` responses use the same
`detail` envelope as other HTTP rejections:
`{"detail": "spawn already terminal: <status>"}`.

**Why.** `spec/http_surface.md` already standardizes rejected HTTP
responses on FastAPI's `detail` form. Keeping cancel on that envelope
avoids a one-off body contract that clients and smoke tests would have
to special-case.

### D-22 — Delete the peercred-unavailable header workaround

**Choice.** No `X-Meridian-Caller` / `X-Meridian-Depth` fallback exists in
this design. Peercred failure on HTTP/socket lifecycle surfaces is an
unconditional deny.

**Why.** The workaround was only partially specified and reintroduced the
fail-open ambiguity D-19 was meant to remove. A forgeable header is still
a different trust boundary, even in an honest-actors model; if Meridian
wants a peercred-unavailable path later, it should be designed as a real
transport, not as an exception bolted onto the deny path.

### D-23 — PID-reuse guard converts `started_at` at read time

**Choice.** D-15 is realized by converting `SpawnRecord.started_at`
(ISO 8601 string) to epoch inside `SignalCanceller._resolve_runner_pid`.
This cleanup round does not add a new `started_epoch` field to the spawn
schema.

**Why.** The existing schema already contains the needed timestamp. Adding
another persisted field would widen R-11 for no behavioral gain.

### D-24 — `inbound_seq` comes from `_record_inbound` return value

**Choice.** R-02 explicitly changes `_record_inbound` to return the
zero-based appended line index and threads that through `InjectResult`.

**Why.** `inbound.jsonl` is the durable ordering authority. Returning the
line index avoids inventing a second sequence source just to satisfy the
HTTP/control-socket acknowledgement contract.
