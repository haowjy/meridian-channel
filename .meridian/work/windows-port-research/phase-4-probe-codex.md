# Phase 4 Probe: codex termination behavior

## Verdict

For `codex`, both direct-child `SIGTERM` and top-level `killpg(top_pgid)` leak the real background grandchild spawned by the tool command. A recursive descendant walk rooted at the wrapper PID terminates the whole tree cleanly. That means the proposed Phase 4 `terminate_tree(proc, grace)` primitive is the right direction for this harness too; porting current Unix `killpg` semantics as-is would preserve a real leak.

## Harness invocation

Each run used `setsid` so the top-level wrapper PID was also the session/process-group leader, matching Meridian's launch shape while still probing the harness binary directly:

```bash
setsid /home/jimyao/.nvm/versions/node/v24.13.0/bin/codex exec \
  --dangerously-bypass-approvals-and-sandbox \
  --color never \
  -C /home/jimyao/gitrepos/meridian-cli \
  - < /tmp/meridian-pgprobe-codex-A.prompt
```

The prompt content was the same shape in each run, with only the run letter changing in `/tmp` paths:

```text
Use exactly one shell command: bash -lc "sleep 600 </dev/null >/tmp/meridian-pgprobe-codex-A-grandchild.out 2>&1 & echo $! > /tmp/meridian-pgprobe-codex-A-grandchild.pid; sleep 600". After starting that command, do not interrupt it or run any other shell command.
```

## Run A: direct-child SIGTERM

- Process tree before kill:

```text
    PID    PPID    PGID     SID STAT COMMAND         COMMAND
3758698 3758696 3758698 3758698 SNsl MainThread      node /home/jimyao/.nvm/versions/node/v24.13.0/bin/codex exec --dangerously-bypass-approvals-and-sandbox --color never -C /home/jimyao/gitrepos/meridian-cli -
3758709 3758698 3758698 3758698 SNl  codex           /home/jimyao/.nvm/versions/node/v24.13.0/lib/node_modules/@openai/codex/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/codex/codex exec --dangerously-bypass-approvals-and-sandbox --color never -C /home/jimyao/gitrepos/meridian-cli -
3759194 3758709 3759194 3759194 SNs  sleep           sleep 600
3759199 3759194 3759194 3759194 SN   sleep           sleep 600
```

- Pstree output:

```text
MainThread,3758698 /home/jimyao/.nvm/versions/node/v24.13.0/bin/codex exec --dangerously-bypass-approvals-and-sandbox --color ...
  |-codex,3758709
  |   |-sleep,3759194 600
  |   |   `-sleep,3759199 600
  |   |-{codex},3758710
  |   |-{codex},3758711
  |   |-{codex},3758712
  |   |-{codex},3758713
  |   |-{codex},3758714
  |   |-{codex},3758715
  |   |-{codex},3758716
  |   |-{codex},3758717
  |   |-{codex},3758718
  |   |-{codex},3758719
  |   |-{codex},3758720
  |   |-{codex},3758721
  |   |-{codex},3758722
  |   |-{codex},3758723
  |   |-{codex},3758724
  |   |-{codex},3758725
  |   |-{codex},3758726
  |   |-{codex},3758727
  |   |-{codex},3758728
  |   |-{codex},3758729
  |   |-{codex},3758730
  |   |-{codex},3758731
  |   |-{codex},3758732
  |   |-{codex},3758733
  |   |-{codex},3758734
  |   |-{codex},3758786
  |   |-{codex},3758787
  |   |-{codex},3758804
  |   |-{codex},3758806
  |   |-{codex},3758843
  |   |-{codex},3758844
  |   |-{codex},3758845
  |   |-{codex},3758846
  |   `-{codex},3758847
  |-{MainThread},3758701
  |-{MainThread},3758702
  |-{MainThread},3758703
  |-{MainThread},3758704
  |-{MainThread},3758705
  `-{MainThread},3758706
```

- Kill command:

```bash
kill -TERM 3758698
```

- Survivors after 2s:

```text
    PID    PPID    PGID     SID STAT COMMAND         COMMAND
3759199       1 3759194 3759194 SN   sleep           sleep 600
```

- Interpretation:
The wrapper and embedded `codex` process exited, but the real background grandchild survived and was reparented to PID 1. By the time the snapshot was taken there was no persistent shell PID; the `bash -lc` layer had already reduced to the foreground/background `sleep` pair. Direct-child termination is insufficient for this harness.

## Run B: top-level killpg

- Process tree before kill:

```text
    PID    PPID    PGID     SID STAT COMMAND         COMMAND
3759490 3759488 3759490 3759490 SNsl MainThread      node /home/jimyao/.nvm/versions/node/v24.13.0/bin/codex exec --dangerously-bypass-approvals-and-sandbox --color never -C /home/jimyao/gitrepos/meridian-cli -
3759499 3759490 3759490 3759490 SNl  codex           /home/jimyao/.nvm/versions/node/v24.13.0/lib/node_modules/@openai/codex/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/codex/codex exec --dangerously-bypass-approvals-and-sandbox --color never -C /home/jimyao/gitrepos/meridian-cli -
3760095 3759499 3760095 3760095 SNs  sleep           sleep 600
3760101 3760095 3760095 3760095 SN   sleep           sleep 600
```

- Pstree output:

```text
MainThread,3759490 /home/jimyao/.nvm/versions/node/v24.13.0/bin/codex exec --dangerously-bypass-approvals-and-sandbox --color ...
  |-codex,3759499
  |   |-sleep,3760095 600
  |   |   `-sleep,3760101 600
  |   |-{codex},3759500
  |   |-{codex},3759501
  |   |-{codex},3759502
  |   |-{codex},3759503
  |   |-{codex},3759504
  |   |-{codex},3759505
  |   |-{codex},3759506
  |   |-{codex},3759507
  |   |-{codex},3759508
  |   |-{codex},3759509
  |   |-{codex},3759510
  |   |-{codex},3759511
  |   |-{codex},3759512
  |   |-{codex},3759513
  |   |-{codex},3759514
  |   |-{codex},3759515
  |   |-{codex},3759516
  |   |-{codex},3759517
  |   |-{codex},3759518
  |   |-{codex},3759519
  |   |-{codex},3759520
  |   |-{codex},3759521
  |   |-{codex},3759522
  |   |-{codex},3759523
  |   |-{codex},3759524
  |   |-{codex},3759576
  |   |-{codex},3759577
  |   |-{codex},3759594
  |   |-{codex},3759596
  |   |-{codex},3759633
  |   |-{codex},3759634
  |   |-{codex},3759635
  |   |-{codex},3759636
  |   `-{codex},3759637
  |-{MainThread},3759493
  |-{MainThread},3759494
  |-{MainThread},3759495
  |-{MainThread},3759496
  |-{MainThread},3759497
  `-{MainThread},3759498
```

- Kill command:

```bash
kill -TERM -3759490
```

- Survivors after 2s:

```text
    PID    PPID    PGID     SID STAT COMMAND         COMMAND
3760101       1 3760095 3760095 SN   sleep           sleep 600
```

- Interpretation:
The current Unix-style `killpg(top_pgid)` strategy also leaked the real background grandchild. The long-running tool subtree had already moved into its own session/process group (`pgid=sid=3760095`), so signaling the wrapper's process group did not reach it.

## Run C: psutil recursive terminate

- Process tree before kill:

```text
    PID    PPID    PGID     SID STAT COMMAND         COMMAND
3760752 3760750 3760752 3760752 SNsl MainThread      node /home/jimyao/.nvm/versions/node/v24.13.0/bin/codex exec --dangerously-bypass-approvals-and-sandbox --color never -C /home/jimyao/gitrepos/meridian-cli -
3760761 3760752 3760752 3760752 SNl  codex           /home/jimyao/.nvm/versions/node/v24.13.0/lib/node_modules/@openai/codex/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/codex/codex exec --dangerously-bypass-approvals-and-sandbox --color never -C /home/jimyao/gitrepos/meridian-cli -
3761510 3760761 3761510 3761510 SNs  sleep           sleep 600
3761520 3761510 3761510 3761510 SN   sleep           sleep 600
```

- Pstree output:

```text
MainThread,3760752 /home/jimyao/.nvm/versions/node/v24.13.0/bin/codex exec --dangerously-bypass-approvals-and-sandbox --color ...
  |-codex,3760761
  |   |-sleep,3761510 600
  |   |   `-sleep,3761520 600
  |   |-{codex},3760762
  |   |-{codex},3760763
  |   |-{codex},3760764
  |   |-{codex},3760765
  |   |-{codex},3760766
  |   |-{codex},3760767
  |   |-{codex},3760768
  |   |-{codex},3760769
  |   |-{codex},3760770
  |   |-{codex},3760771
  |   |-{codex},3760772
  |   |-{codex},3760773
  |   |-{codex},3760774
  |   |-{codex},3760775
  |   |-{codex},3760776
  |   |-{codex},3760777
  |   |-{codex},3760778
  |   |-{codex},3760779
  |   |-{codex},3760780
  |   |-{codex},3760781
  |   |-{codex},3760782
  |   |-{codex},3760783
  |   |-{codex},3760784
  |   |-{codex},3760785
  |   |-{codex},3760786
  |   |-{codex},3760838
  |   |-{codex},3760839
  |   |-{codex},3760856
  |   |-{codex},3760858
  |   |-{codex},3760895
  |   |-{codex},3760896
  |   |-{codex},3760897
  |   |-{codex},3760898
  |   |-{codex},3760899
  |   `-{codex},3760900
  |-{MainThread},3760755
  |-{MainThread},3760756
  |-{MainThread},3760757
  |-{MainThread},3760758
  |-{MainThread},3760759
  `-{MainThread},3760760
```

- Kill command:

```bash
uv run python -c '
import psutil, time, sys
root = psutil.Process(int(sys.argv[1]))
descendants = root.children(recursive=True)
all_procs = [root, *descendants]
for p in all_procs:
    try:
        p.terminate()
    except psutil.NoSuchProcess:
        pass
gone, alive = psutil.wait_procs(all_procs, timeout=3)
for p in alive:
    try:
        p.kill()
    except psutil.NoSuchProcess:
        pass
' 3760752
```

- Survivors after 2s:

```text
    PID    PPID    PGID     SID STAT COMMAND         COMMAND
```

- Interpretation:
Recursive descendant termination contained the full tree, including the background grandchild that had escaped Runs A and B. No tracked PID survived the terminate-then-kill fallback.

## Cross-cuts vs Codex probe

- Same leak pattern as the existing `.meridian/work/windows-port-research/phase-4-probe.md` Codex evidence: direct-child `SIGTERM` leaks the background grandchild.
- Same leak pattern for current Unix `killpg(top_pgid)`: the descendant subtree can move into its own session/process group, so top-level group signaling does not reach it.
- New evidence here is positive, not just negative: the proposed recursive `psutil.Process.children(recursive=True)` strategy actually contains the tree for this harness.
- Net implication: Phase 4 should be a both-platforms termination semantic upgrade, not a Windows-only shim. The primitive needs descendant enumeration, not just top-level process-group signaling.

## Confidence

High. The result is based on three fresh real harness runs with unique PIDs, real `ps`/`pstree` captures, and explicit cleanup between runs. Runs A and B reproduced the leak with separate PID sets, and Run C eliminated the same class of survivor entirely.
