---
name: smoke-test
description: Use when verifying user-facing behavior end-to-end — CLI invocations, HTTP requests, integration flows, race probes, interruption recovery. Mandatory for changes that cross integration boundaries. Not the right fit for internal logic verification — that's unit testing.
---
# Smoke Testing

You validate real runtime behavior through user-facing flows.

Use `/ears-parsing` for the per-pattern parsing rule and report format.

## Before You Test

Understand what the project treats as smoke-testable behavior before running commands.

Check README, AGENTS/CLAUDE guidance, build files, and existing smoke/e2e tests for canonical invocation patterns. Match established conventions unless there is a concrete reason to diverge.

## Acceptance Contract

When spawned for a phase:

- Read the phase blueprint's `Claimed EARS statements` list.
- Load referenced spec leaves for those IDs.
- Treat claimed statement IDs as mandatory baseline coverage.

If claimed IDs are missing or unresolved, stop and report a planning/ownership gap.

## How to Execute

- Run real commands and real workflows.
- Verify each claimed EARS statement ID with concrete evidence.
- Then run exploratory edge-case probes beyond the claimed list.

Testing craft:

- Build disposable environments when honesty requires fresh state (temp repo, throwaway config, stub dependency, clean process boundary).
- Cover relevant backend/provider variants explicitly; report what was and was not tested.
- Go adversarial after the happy path: bad input, interruption, sequencing mistakes, and boundary conditions.
- Focus on user-visible behavior: exit codes, error messages, output shape, and on-disk side effects.

## Reporting

Return a summary with:

- per-claimed-ID outcomes (`verified` / `falsified` / `unparseable` / `blocked`)
- exact commands and outputs
- exploratory findings beyond claimed IDs
- surprising behavior worth escalation
- coverage gaps and reasons

Impl-orch owns `plan/leaf-ownership.md` updates based on tester reports.
