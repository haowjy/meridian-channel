---
name: ears-parsing
description: Mechanical EARS verification contract for testers. Use when phase verification is keyed to claimed EARS statement IDs and you need to turn each statement into trigger, fixture, assertion, and report outcome.
---

# EARS Parsing

Apply a mechanical parse for each claimed EARS statement ID.

Outcome must be reported per statement ID as one of: `verified`, `falsified`, `unparseable`, or `blocked`.

## Pattern Table

| Pattern letter | Pattern | Trigger | Fixture | Assertion |
|---|---|---|---|---|
| `u` | Ubiquitous | bring system to normal running mode | default running state | `shall` clause holds as invariant |
| `s` | State-driven | execute operation while state is active | `while` clause | `shall` clause, including negative form |
| `e` | Event-driven | `when` clause event | implicit defaults if needed | `shall` clause |
| `w` | Optional-feature | operate with feature enabled | `where` clause (feature/config enabled) | `shall` clause |
| `c` | Complex | `when` clause | `while` clause | `shall` clause |

## Escape Valve

If a statement does not parse mechanically from its pattern and context, report:

`<statement-id>: unparseable (mechanical parse failed; requires design clarification)`

Use `unparseable` when the statement does not mechanically parse to a reproducible verification contract.

## Reporting Discipline

For each claimed statement ID include:

- outcome
- command/test evidence
- observed result
- expected result when falsified

Tester lanes report. Impl-orch updates `plan/leaf-ownership.md`.
