# Concurrency Review

Think about what happens when two things run at the same time. Then think about what happens when one of them is cancelled halfway through.

## Shared Mutable State

The root of most concurrency bugs. For every piece of shared state, ask:

- **Who can read and write it?** If multiple threads/tasks/processes can write, how is access synchronized?
- **What's the granularity?** A lock around a single field doesn't help if the invariant spans multiple fields that need to update atomically.
- **Read-modify-write** — The classic race. Check-then-act patterns (if not exists, create) are almost always racy without synchronization.

## Common Patterns to Look For

**Races** — Two operations that assume they're the only one running. Look for: file creation without exclusive flags, database updates without transactions or optimistic locking, in-memory state modified without locks.

**Deadlocks** — Two locks acquired in different orders by different code paths. If you see nested locking, check whether all callers acquire in the same order.

**Stale reads** — Reading a value, doing work, then acting on it — but the value changed in between. Common with caches, status checks, and configuration.

**Resource leaks under cancellation** — If a task is cancelled or times out, are file handles closed? Locks released? Temporary files cleaned up? The happy path might clean up fine while the cancellation path leaks.

**Ordering assumptions** — "This always runs before that" without enforcement. Startup ordering, event processing, callback registration — any implicit ordering dependency is fragile.

**Goroutine/thread leaks** — Spawned work that never terminates. Look for goroutines or threads waiting on channels/events that nothing will ever send on.

## What Good Looks Like

A concurrency finding should describe the interleaving that causes the bug, not just say "this might race." Walk through the steps: "Thread A reads the counter, thread B increments and writes, thread A writes the stale value — the increment is lost."
