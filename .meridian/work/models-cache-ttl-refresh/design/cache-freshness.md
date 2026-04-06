# Cache Freshness

## Definition

The models cache is **fresh** iff *all* of the following hold:

1. `.mars/models-cache.json` exists and parses as a valid `ModelsCache`.
2. It has a non-empty `fetched_at` field that parses as a timestamp.
3. `now_unix() - fetched_at_unix() < ttl_hours * 3600`.

Any other state — missing file, missing `fetched_at`, unparseable
`fetched_at`, negative delta (clock skew), delta ≥ TTL — counts as **stale**.

A TTL of `0` is a special case: every read is stale, every `Auto` call
refreshes. Useful for tests and CI.

## `fetched_at` Format

The existing `now_iso()` helper in `src/cli/models.rs` is mis-named — it
writes a bare Unix-seconds integer as a string (e.g. `"1712345678"`), not an
ISO-8601 timestamp. The name is preserved for now, but the TTL check must
parse **either**:

- **Unix seconds string** (current format, written by `now_iso()` today).
  Parse as `u64`.
- **ISO-8601 UTC** (reserved for future use) — skip for this work item;
  document that the format may evolve and callers should not depend on it
  being human-readable.

Going forward, `ensure_fresh` writes `fetched_at` using the same
Unix-seconds format the current `now_iso()` produces. The rename to
something honest (`now_unix_secs()`) is a drive-by cleanup — the existing
mis-name is a Chesterton's fence worth removing because the string
"`now_iso`" actively misleads any future reader.

## Legacy / Partial Caches

Three degenerate inputs are possible:

| On-disk state                            | Treated as |
|------------------------------------------|------------|
| File missing                             | Stale (no existing cache) |
| File present, `fetched_at = None`        | Stale (with existing cache) |
| File present, `fetched_at` unparseable   | Stale (with existing cache) |
| File present, `fetched_at` in future     | Stale (with existing cache; log warn) |
| File present, corrupt JSON               | Stale (with *no* existing cache) — `ensure_fresh` treats unparseable like absent |

"Stale with existing cache" vs "stale with no existing cache" matters for the
offline-fallback path — the former can degrade gracefully on fetch failure;
the latter cannot.

## No Migration

Existing `.mars/models-cache.json` files without `fetched_at` are *not*
rewritten on startup. They're silently refreshed on next `Auto` call. This
keeps the upgrade path zero-friction and avoids a one-shot migration routine.

## Why Not Mtime?

File mtime would work but is brittle: `cp -a`, `git checkout`, and container
image bakes all preserve stale mtimes or reset fresh ones. Embedding
`fetched_at` inside the JSON is explicit, portable, and already half-built
(the field exists on `ModelsCache`).
