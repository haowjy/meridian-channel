# State Safety Review

Static review of the state layer and related launch paths, focused on correctness, crash safety, and concurrency.

`MERIDIAN_WORK_DIR` was unset in this environment, so this review was written to `.meridian/work/review-state-safety.md`.

## Findings

### 1. High: `active-primary.lock` is not actually providing mutual exclusion, and stale-lock cleanup can delete a live launch marker

- `src/meridian/lib/launch/process.py:86-99` only writes a JSON file; there is no `flock`, `O_EXCL`, or pre-launch existence check anywhere in the primary launch path.
- `src/meridian/lib/launch/process.py:478-482` first writes the lock with `child_pid=None`, then rewrites it after the child starts.
- `src/meridian/lib/launch/process.py:115-137` treats missing/zero `child_pid` as orphaned and unlinks the file without checking whether `parent_pid` is still alive.

Impact:
- Two primary launches are not serialized by this "lock".
- A concurrent CLI startup can delete a valid lock during the pre-child window and allow another primary launch to proceed.
- If the launcher dies before rewriting `child_pid`, stale-lock cleanup cannot distinguish "launcher still starting" from "orphaned".

### 2. High: both background and foreground spawns have a crash window where a live child can be marked orphaned because the PID is persisted too late

- Background path:
  `src/meridian/lib/ops/spawn/execute.py:720-759` starts the detached worker before writing `background.pid` and before `mark_spawn_running(...)`.
- Foreground primary path:
  `src/meridian/lib/launch/process.py:478-492` starts the harness before writing `harness.pid` and before `mark_spawn_running(...)`.
- Reconciliation assumes the PID file/update must exist after grace:
  `src/meridian/lib/state/reaper.py:390-415` and `src/meridian/lib/state/reaper.py:438-460`.

Impact:
- If the parent crashes after `Popen`/`pty.fork` succeeds but before the PID/update is durably written, the child can keep running while reaper later finalizes it as `missing_wrapper_pid`, `missing_worker_pid`, or `orphan_launch`.
- This violates the crash-only expectation that recovery converges to the real on-disk/process state.

### 3. High: `start_session()` can deadlock across processes when reusing an active `chat_id`

- `src/meridian/lib/state/session_store.py:246-267` acquires `sessions.lock`, appends the `start` event, then blocks acquiring `sessions/<chat_id>.lock`.
- `src/meridian/lib/state/session_store.py:275-277` requires `sessions.lock` before `stop_session()` can release that same per-session lock.

Impact:
- If process A owns `sessions/<chat_id>.lock` and process B tries to `start_session(chat_id=...)`, process B can hold `sessions.lock` while waiting for the per-session lock.
- Process A then blocks in `stop_session()` waiting for `sessions.lock`.
- That is a lock-order inversion and a real deadlock.

### 4. High: `start_session()` records an active session before acquiring the lifetime lock, so crashes can strand sessions in a permanently-active state

- `src/meridian/lib/state/session_store.py:246-267` appends the `start` event before acquiring `sessions/<chat_id>.lock`.
- `src/meridian/lib/state/session_store.py:404-448` only cleans up sessions that still have a lock file.
- `src/meridian/lib/state/session_store.py:381-401` treats any `start` without `stop` as active.

Impact:
- If the process dies after appending the `start` event but before creating/locking `sessions/<chat_id>.lock`, there is no lock file for `cleanup_stale_sessions()` to discover.
- The session remains logically active forever in `sessions.jsonl`, which can block cleanup/materialization decisions.

### 5. High: work-item rename/update is not concurrency-safe and can recreate the old work directory after a rename

- `src/meridian/lib/state/work_store.py:152-183` renames `work/<old>` to `work/<new>`.
- `src/meridian/lib/state/work_store.py:186-208` does an unsynchronized read/modify/write to `work/<work_id>/work.json`.
- `src/meridian/lib/state/atomic.py:26-37` recreates parent directories during `atomic_write_text(...)`.

Impact:
- If one process reads `old-name`, another renames it to `new-name`, and the first process then calls `update_work_item(old-name, ...)`, `atomic_write_text()` recreates `work/old-name/` and writes a fresh `work.json`.
- You can end up with both `work/old-name/` and `work/new-name/` on disk, with no repair logic.

### 6. Medium: `rename_work_item()` is not crash-atomic and can leave self-contradictory work state

- `src/meridian/lib/state/work_store.py:174-182` renames the directory first and only then rewrites `work.json` with the new slug.
- `src/meridian/lib/state/work_store.py:135-149` trusts the `work.json` payload when listing work items.

Impact:
- A crash after the directory move but before the JSON rewrite leaves `work/new-name/work.json` still reporting `"name": "old-name"`.
- Reads can then surface a work item whose directory and payload disagree.

### 7. Medium: stale detection will false-fail healthy but quiet spawns

- `src/meridian/lib/state/reaper.py:99-116` marks a spawn stale based only on `output.jsonl`, `stderr.log`, or PID-file age.
- `src/meridian/lib/state/reaper.py:410-415` and `src/meridian/lib/state/reaper.py:455-460` fail the spawn even if the observed PID is still alive.

Impact:
- Any harness that buffers output or spends more than 5 minutes in a quiet tool call can be marked `stale`, signaled, and finalized as failed while still healthy.
- This is a read-path false positive, not a true crash recovery.

### 8. Medium: `collect_active_chat_ids()` is wrong for reused chat IDs because it ignores event order

- Reuse is explicitly supported by `src/meridian/lib/state/session_store.py:246-250` and covered in `tests/test_state/test_session_store.py:122-148`.
- `src/meridian/lib/state/session_store.py:392-399` computes active sessions as `started - stopped` using sets.

Impact:
- Event sequence `start(c7)`, `stop(c7)`, `start(c7)` still yields `started={"c7"}`, `stopped={"c7"}`, so the function reports no active session.
- `src/meridian/lib/launch/process.py:171-183` uses this signal to decide whether orphaned materializations should be swept, so a live resumed session can be treated as inactive.

## Notes

- The JSONL append paths for `spawns.jsonl` and `sessions.jsonl` are serialized with `fcntl.flock` on sidecar lock files and tolerate truncated trailing lines reasonably well.
- I did not find a schema-version migration path beyond storing `v=1`; the code does not branch on `v`, so forward-compatibility is weak even though unknown extra fields are ignored.
- State-adjacent stream artifacts (`output.jsonl`, `stderr.log`) are written directly rather than via atomic replace. That is probably acceptable for append/capture logs, but it does not satisfy the literal "every write is atomic" claim.

## Verification

- Static review only.
- No tests or smoke runs were executed.
