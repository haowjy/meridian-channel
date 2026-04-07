# Consumer Profile Updates

Every agent profile that lists a deleted skill in its `skills:` array, and every body-text reference to one of those skills, must be updated. This doc enumerates the exact set found in both submodules.

## Search Methodology

Looking for any non-`.agents/` reference to:

- `__mars`
- `__meridian-diagnostics`
- `__meridian-session-context`

across `meridian-base/` and `meridian-dev-workflow/` (the source submodules).

## Findings

### `__mars` references

**None.** No agent profile in either submodule lists `__mars` in its skills array. The skill is loaded ad-hoc by orchestrators as needed. Only README mentions exist:

- `meridian-base/README.md:48` — table entry. Update to remove the row (or replace with `__meridian-cli`).

### `__meridian-diagnostics` references

**None.** No profile lists it. README mention only:

- `meridian-base/README.md:49` — table entry. Update to remove the row.

### `__meridian-session-context` references

| File | Line | What | Fix |
|---|---|---|---|
| `meridian-base/README.md` | 47 | Table entry | Remove row (skill is being deleted from base) |
| `meridian-dev-workflow/README.md` | 118 | Bullet "(base)" reference | Replace with `session-mining` (dev-workflow) and `__meridian-cli` (base, if relevant) |
| `meridian-dev-workflow/agents/code-documenter.md` | 10 | `skills: [..., __meridian-session-context, decision-log]` | Replace `__meridian-session-context` with `session-mining`. Add `__meridian-cli` if the profile depends on the CLI half. |
| `meridian-dev-workflow/agents/code-documenter.md` | 74 | Body text: `Use /__meridian-session-context to search and navigate transcripts` | Rewrite to point at `/session-mining` for the workflow pattern; let the CLI half come from `__meridian-cli`. |
| `meridian-dev-workflow/agents/dev-orchestrator.md` | 10 | `skills: [..., __meridian-session-context, ...]` | Same skill swap. Add `__meridian-cli` explicitly. |
| `meridian-dev-workflow/agents/docs-orchestrator.md` | 12 | `skills: [..., __meridian-session-context, ...]` | Same skill swap. Add `__meridian-cli` explicitly. |
| `meridian-dev-workflow/agents/docs-orchestrator.md` | 44 | Body: `Use /__meridian-session-context to search transcripts...` | Rewrite to `/session-mining`. |

### Other base agents

- `meridian-base/agents/__meridian-orchestrator.md` (line 29): the `@reviewers` generic-guidance leak (see `05-cross-layer-leaks.md`). Skills array is unaffected.
- `meridian-base/agents/__meridian-subagent.md`: empty skills array, unchanged.

## `__meridian-cli` Adoption

The new skill should be added to the `skills:` array of every profile that previously had a transitive dependency on the CLI reference content of any deleted skill. The conservative set:

| Profile | Add `__meridian-cli`? | Rationale |
|---|---|---|
| `dev-orchestrator` | **Yes** | Diagnoses spawn failures, mines sessions, runs `meridian config`-style introspection |
| `docs-orchestrator` | **Yes** | Mines sessions, manages work artifacts, runs reports |
| `code-documenter` | **Yes** | Reads spawn reports and session logs |
| `__meridian-orchestrator` (base) | **No** | Already minimal; loads CLI skills ad-hoc when needed |
| `__meridian-subagent` (base) | **No** | Empty profile by design |
| All other dev-workflow agents (reviewer, coder, planner, etc.) | **Sweep and decide per profile** | Most don't need it. The planner should grep the body for any meridian/mars CLI usage and add the skill only where it's actually called for. |

## README Updates

Both `meridian-base/README.md` and `meridian-dev-workflow/README.md` have skill tables that enumerate what each package ships. After consolidation:

- meridian-base README: remove `__mars`, `__meridian-diagnostics`, `__meridian-session-context` rows. Add `__meridian-cli` row.
- meridian-dev-workflow README: remove the line referencing `__meridian-session-context (base)`. Add a line for the new `session-mining` skill.

## Verification

After all profile updates, the project itself runs `meridian mars sync` and verifies:

1. No profile in either submodule references a deleted skill.
2. Every profile that adds `__meridian-cli` actually loads it (check `.agents/` after sync).
3. `meridian mars doctor` reports clean.
4. A smoke test: `meridian spawn -a dev-orchestrator --dry-run -p "test"` resolves the profile without error.

The planner should bundle this verification into the final phase.
