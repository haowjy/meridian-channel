# Design Review Areas

Reference material for both the orchestrator (selecting review focus areas) and reviewers (knowing what to look for). Load this before spawning design reviewers or when conducting a design review yourself.

## Design Review vs. Code Review

Design review evaluates an approach, not an implementation. The question isn't "is this code correct?" but "will this approach work when someone builds it? Will it scale? Will it paint us into a corner?"

This means you're reading prose and diagrams, not diffs. You're looking for flawed reasoning, missing considerations, and unstated assumptions — not style issues or off-by-one errors. Those come later, during code review, when there's code to review.

A good design review catches problems that are expensive to fix after implementation starts. A design change is a paragraph rewrite. An architecture change after three phases of implementation is a project.

## Areas to Evaluate

Not all areas apply to every design. The orchestrator picks the most relevant ones and includes them in the reviewer's prompt.

### Feasibility

Can this actually be built as described? Look for:

- Dependencies on libraries, services, or APIs that may not behave as assumed
- Performance assumptions that aren't validated (e.g., "this query will be fast" without indexing analysis)
- Hidden prerequisites — things that need to exist before this design can work but aren't mentioned
- Complexity that's been hand-waved ("the sync logic will handle edge cases" — which edge cases?)

The goal isn't to prove it's impossible. It's to find the gaps between the design's assumptions and reality before a coder hits them mid-implementation.

### Scope Boundaries

Is the scope well-defined? Look for:

- Vague boundaries where scope could expand during implementation ("and related functionality")
- Out-of-scope items that are actually necessary for the in-scope work to function
- Implicit scope — things the design assumes will happen but doesn't list as in-scope
- Scope that's too large to implement coherently in one work item

A well-scoped design makes it obvious what's included and what isn't. If you have to guess whether something is in scope, the boundary needs sharpening.

### Integration Risks

How does this connect to existing systems? Look for:

- Assumptions about existing APIs, data formats, or behavior that may be wrong
- Changes to shared interfaces that affect other consumers
- Missing coordination with concurrent work items touching the same area
- Data migration needs that aren't addressed in the design

Integration risks are the most common source of design failures. The design works in isolation but breaks when it meets the real codebase.

### Scalability

Does this approach work beyond current conditions? Look for:

- Data structures or algorithms with non-obvious scaling characteristics
- Synchronous operations that become bottlenecks under load
- State accumulation without cleanup or rotation
- Single points of failure or contention

Not every design needs scalability review. A CLI tool used by 5 developers doesn't need to handle 10,000 concurrent users. Apply this lens when the design involves data pipelines, shared services, storage systems, or anything that processes growing amounts of data.

### Security Implications

Does this introduce new risk? Look for:

- New attack surface (new endpoints, new input channels, new data flows)
- Changes to trust boundaries (who can access what, and how is that enforced?)
- Credential or secret handling (storage, transmission, rotation)
- Input that flows from untrusted sources to sensitive operations without validation

Like scalability, not every design needs security review. An internal refactor with no new inputs or outputs probably doesn't. A new API endpoint that accepts user data definitely does.

### Migration Path

If this changes existing behavior, how do we get from here to there? Look for:

- Whether the migration can be done incrementally or requires a big-bang cutover
- Backward compatibility during the transition (can old and new coexist?)
- Rollback strategy if the migration goes wrong
- Data migration needs and whether they're reversible

Skip this area for greenfield work. Apply it when the design replaces, modifies, or extends something that's already running.

### Alternative Approaches

Were alternatives considered? Look for:

- Whether the design doc discusses why this approach over others
- Obvious alternatives that weren't mentioned (a reviewer's fresh perspective catches these)
- Conditions that would make an alternative approach better — these become useful if the design's assumptions change later

If the design doc doesn't mention alternatives, that's a finding in itself. Either the authors didn't consider them (risky) or they did but didn't record why they chose this one (lost context).

### Testability

Can this design be verified? Look for:

- Whether the key behaviors can be tested without elaborate setup
- Observable success criteria — how would you know it's working correctly?
- Failure modes that are hard to reproduce in testing
- Whether the design creates tight coupling that makes unit testing difficult

A design that's hard to test is often a design with unclear boundaries or too many hidden dependencies.

## How the Orchestrator Uses This

When spawning design reviewers, include the specific areas most relevant to the design. Typically 2-4 areas per reviewer — enough to focus deeply, few enough to avoid shallow coverage.

```bash
# For a new API feature:
meridian spawn -a reviewer-planning \
  -p "Review this design. Focus on: feasibility, integration risks, security implications." \
  -f $MERIDIAN_WORK_DIR/overview.md -f $MERIDIAN_WORK_DIR/decision-log.md

# For an internal refactor:
meridian spawn -a reviewer-solid \
  -p "Review this design. Focus on: scope boundaries, migration path, alternative approaches." \
  -f $MERIDIAN_WORK_DIR/overview.md -f $MERIDIAN_WORK_DIR/decision-log.md
```

Different reviewers can cover different areas. If you spawn two reviewers, split the areas between them rather than giving both the same list.

## How Reviewers Use This

When you're reviewing a design (not code), focus on approach-level concerns:

- Flag risks the authors may not have considered
- Identify assumptions that aren't validated or stated
- Point out missing considerations — things the design should address but doesn't
- Suggest alternatives when you see problems, not just "this won't work"

Severity still applies. A feasibility problem that makes the design unbuildable is CRITICAL. A missing discussion of alternatives is MEDIUM. Use the same severity framework as code review — it gives the orchestrator a consistent way to triage across both design and code review findings.
