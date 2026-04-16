# Phase 4 Probe: process-group termination machinery

## Verdict

**Load-bearing** for the narrow question "can we replace kill-by-group with `Popen.terminate()` on the direct child?" Real Codex harness descendants survive that.

But the probe also found a more important nuance: **the current top-level `killpg(top_pgid, ...)` semantics are not sufficient either** for Codex background tool descendants that move into their own session/process group. Phase 4 should not delete termination machinery, but it also should not treat "Windows port of current top-level `killpg`" as the final answer.

## Evidence

### Code audit

- [`src/meridian/lib/launch/runner.py:239`](../../../../src/meridian/lib/launch/runner.py:239) launches the harness with `start_new_session=True`, so the direct child becomes a new session/process-group leader.
- [`src/meridian/lib/launch/signals.py:21`](../../../../src/meridian/lib/launch/signals.py:21) sends signals only to `os.killpg(os.getpgid(pid), signum)`.
- [`src/meridian/lib/launch/timeout.py:21`](../../../../src/meridian/lib/launch/timeout.py:21) explicitly documents that descendants can inherit harness pipes and keep exit observation complicated.
- [`src/meridian/lib/ops/spawn/api.py:488`](../../../../src/meridian/lib/ops/spawn/api.py:488) `spawn.cancel` resolves one PID and sends `SIGTERM` to that PID. The recursive cleanup story lives lower in the runner.

### Real harness probe: direct-child SIGTERM

Command used:

```bash
printf 'HARNESSPID:%s\n' $$; exec codex --no-alt-screen --model gpt-5.4-mini \
  --dangerously-bypass-approvals-and-sandbox \
  -C /home/jimyao/gitrepos/meridian-cli \
  "Use exactly one shell command: bash -lc \"sleep 600 </dev/null >/tmp/meridian-pgprobe-codex3-grandchild.out 2>&1 & echo \$! > /tmp/meridian-pgprobe-codex3-grandchild.pid; sleep 600\". After starting that command, do not interrupt it or run any other shell command."
```

Observed process tree before termination:

```text
2630246  node wrapper   ppid=2623587 pgid=2630246 sid=2630246
2630255  codex binary   ppid=2630246 pgid=2630246 sid=2630246
2630990  sleep 600      ppid=2630255 pgid=2630990 sid=2630990
2630995  sleep 600      ppid=2630990 pgid=2630990 sid=2630990
```

`pstree -ap 2630246` showed:

```text
MainThread,2630246 .../bin/codex
  `-codex,2630255
      `-sleep,2630990 600
          `-sleep,2630995 600
```

Termination step:

```bash
kill -TERM 2630246
```

Observed after 2s:

```text
2630995       1 2630990 2630990 SN   sleep  sleep 600
```

Interpretation:

- Sending `SIGTERM` to only the direct child killed the top Codex process and its immediate descendants.
- A real background grandchild (`2630995`) survived and was re-parented to PID 1.

### Real harness probe: top-level process-group SIGTERM

Same prompt shape, new PIDs:

```text
2632510  node wrapper   pgid=2632510 sid=2632510
2632519  codex binary   ppid=2632510 pgid=2632510 sid=2632510
2633345  sleep 600      ppid=2632519 pgid=2633345 sid=2633345
2633350  sleep 600      ppid=2633345 pgid=2633345 sid=2633345
```

Termination step matching Meridian's current Unix semantics:

```bash
kill -TERM -2632510
```

Observed after 2s:

```text
2633350       1 2633345 2633345 SN   sleep  sleep 600
```

Interpretation:

- The top-level process-group kill also leaked the deepest background descendant.
- In this Codex shape, the long-running tool subtree had already moved into its own session/process group (`pgid=sid=2633345`), so `killpg(top_pgid)` did not reach it.

## What this means

- **Do not replace the subsystem with `process.terminate()` on the direct child.** That definitely leaks real harness descendants.
- **Do not assume the current Unix process-group approach is the correct thing to port 1:1 to Windows.** The Codex probe shows top-level group signaling is not enough once descendants create their own session/process group.

## Harnesses tested

- **Codex**: leaked a real background grandchild under both direct-child `SIGTERM` and top-level `killpg(top_pgid)`.
- **Claude / OpenCode**: not empirically probed in this pass.

## Recommendation for Phase 4

Scope Phase 4 as a **termination refactor**, not just a Windows shim:

1. Keep a termination subsystem; do not delete it as phantom.
2. Change the target semantics from "signal the top process group" to "reap the whole descendant tree, including descendants that created their own session/process group".
3. On Windows that likely means `CREATE_NEW_PROCESS_GROUP` for the top-level child plus explicit recursive descendant enumeration/termination (for example via `psutil` or Job Objects).
4. On Unix, consider the same recursive-tree strategy instead of relying only on `killpg(top_pgid, ...)`.

## Confidence

High that `process.terminate()` on the direct child is insufficient.

Medium-high that current top-level `killpg` semantics are also insufficient for Codex specifically, because the empirical probe directly observed the surviving descendant after `kill -TERM -top_pgid`.
