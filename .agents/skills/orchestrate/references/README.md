# Skill Policy References

This directory contains skill policy files used by `load-skill-policy.sh`.

## Override Behavior

- If **any non-default** `.md` files exist in this directory (besides `default.md` and this README), they **replace** `default.md` entirely.
- If only `default.md` exists, it is used as the active policy.
- Custom policy files are loaded in bytewise-lexicographic filename order for determinism.

## Adding Custom Policies

1. Create a new `.md` file in this directory (e.g., `my-project-policy.md`).
2. List one skill name per line (plain text or markdown bullets).
3. The presence of any custom file causes `default.md` to be ignored.

## Format

Each policy file lists recommended skills, one per line:

```
reviewing
scratchpad
researching
```

Or with markdown bullets:

```
- reviewing
- scratchpad
- researching
```
