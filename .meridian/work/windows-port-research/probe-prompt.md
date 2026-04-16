# Probe: harness termination behavior under three strategies

## Why this matters

Meridian's Phase 4 (Windows port) plan reframes process-group machinery into a recursive `terminate_tree(proc, grace)` primitive using `psutil.Process.children(recursive=True)`. That decision was driven by the existing Codex probe at `.meridian/work/windows-port-research/phase-4-probe.md`, which showed:

- Direct-child `SIGTERM` leaks real grandchild
- Top-level `killpg(top_pgid)` *also* leaks grandchild (the long-running tool subtree moved into its own session/pgroup)

We need the same evidence for **{{HARNESS}}** specifically. The Phase 4 termination refactor is a both-platforms change, so getting it wrong on any one harness ships a real Unix bug too.

## Harness under test

`{{HARNESS}}` (binary: `{{HARNESS_BIN}}`)

The other two harnesses are being probed in parallel by sibling investigators. Stay focused on this one.

## Probe protocol

Reproduce the Codex probe shape but for {{HARNESS}}. Three runs, fresh PIDs each time:

### Run A: direct-child SIGTERM

1. Launch the harness in non-interactive mode (figure out the right flags — `--help` is your friend; for codex it was `--no-alt-screen --dangerously-bypass-approvals-and-sandbox -C <repo>`; equivalents exist for claude/opencode).
2. Prompt it to run a shell command that backgrounds a long-lived grandchild and waits in foreground. Pattern that worked for Codex:
   ```
   Use exactly one shell command: bash -lc "sleep 600 </dev/null >/tmp/meridian-pgprobe-{{HARNESS}}-A-grandchild.out 2>&1 & echo $! > /tmp/meridian-pgprobe-{{HARNESS}}-A-grandchild.pid; sleep 600". After starting that command, do not interrupt it or run any other shell command.
   ```
   Adapt the prompt shape so the harness actually executes a shell tool — Claude has a `Bash` tool, OpenCode has its own shell mechanism. The goal: get a real backgrounded grandchild process owned by the harness's tool subtree.
3. Once the grandchild exists (check the pid file), capture:
   - Wrapper PID
   - Harness binary PID
   - Shell PID(s)
   - Foreground `sleep 600` PID
   - Background `sleep 600` PID
   - For each: `ppid`, `pgid`, `sid` via `ps -o pid,ppid,pgid,sid,stat,comm,args -p <pids>`
   - Tree shape via `pstree -ap <wrapper_pid>`
4. Run `kill -TERM <wrapper_pid>` (NOT `-<wrapper_pid>` — direct child only).
5. Wait 2-3s. Capture survivors with `ps -o pid,ppid,pgid,sid,stat,comm,args` filtered by your earlier pids.
6. Clean up any survivors with `kill -KILL` before next run.

### Run B: top-level process-group SIGTERM (current Meridian Unix behavior)

Same setup as Run A, then `kill -TERM -<wrapper_pid>` (note the `-` prefix → killpg). Capture survivors. Clean up.

### Run C: recursive descendant termination (proposed Phase 4 strategy)

Same setup. Then use `psutil` from a Python one-liner to enumerate the entire descendant tree starting from the wrapper PID, terminate them all, wait briefly, kill stragglers:

```bash
uv run python -c "
import psutil, time, sys
root = psutil.Process(int(sys.argv[1]))
descendants = root.children(recursive=True)
all_procs = [root, *descendants]
for p in all_procs:
    try: p.terminate()
    except psutil.NoSuchProcess: pass
gone, alive = psutil.wait_procs(all_procs, timeout=3)
for p in alive:
    try: p.kill()
    except psutil.NoSuchProcess: pass
" <wrapper_pid>
```

Capture survivors. Should be empty.

## What to report

Write findings to `.meridian/work/windows-port-research/phase-4-probe-{{HARNESS}}.md` with this structure:

```markdown
# Phase 4 Probe: {{HARNESS}} termination behavior

## Verdict
One paragraph: which strategies leak descendants for this harness, which contain the tree.

## Harness invocation
The exact non-interactive command line used.

## Run A: direct-child SIGTERM
- Process tree before kill (table of pid/ppid/pgid/sid/comm)
- Pstree output
- Kill command
- Survivors after 2s
- Interpretation

## Run B: top-level killpg
... same shape ...

## Run C: psutil recursive terminate
... same shape ...

## Cross-cuts vs Codex probe
- Same pattern? Different? What does this tell us about the proposed psutil terminate_tree primitive?

## Confidence
High/medium/low, with reasoning.
```

## Constraints

- **Do not modify any source code in this repo.** Read-only investigation.
- **Do not invoke meridian** — probe the harness binary directly. We're checking harness behavior, not meridian's wrapping.
- If the harness refuses to run a backgrounded shell command (sandbox restrictions), document the workaround you used or the failure mode. Don't synthesize fake evidence.
- Use real PIDs from real harness runs. No simulations.
- Clean up your probe processes between runs so they don't pile up.
- Path for /tmp files: include `{{HARNESS}}` and run letter so parallel investigators don't collide.
