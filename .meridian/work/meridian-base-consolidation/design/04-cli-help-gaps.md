# CLI `--help` Gap Analysis

The new `__meridian-cli` skill points at `--help` as the canonical reference. That's only honest if `--help` actually contains what the old skills documented. This doc enumerates the gaps and the proposed additions.

The fixes are **prerequisite** to the consolidation: the help text gets updated *before* the old skills are deleted. Otherwise an agent following the new skill's pointers lands on inadequate text.

These additions live in the meridian source tree (`src/meridian/cli/...`) and the mars source tree, not in the skill bodies. Implementation is part of phase 1 of the eventual plan.

## Gap 1 — `meridian --help` (top-level) is missing command groups

Current top-level help lists only `mars`, `spawn`, `work`, `models`. Missing:

- `session` — subcommand group exists (`session log`, `session search`)
- `config` — subcommand group exists (`config get/set/show/init/reset`)
- `report` — exists as a subcommand of `spawn` but worth surfacing
- `doctor` — top-level command exists

**Add to top-level Commands list:**

```
session  Read and search harness session transcripts
config   Repository config inspection and overrides
doctor   Health check and orphan reconciliation
```

Plus a one-line note that `meridian spawn report` exists for reports management.

## Gap 2 — `meridian doctor --help` is one line

Current text: `Spawn diagnostics checks.`

This is the command the consolidation skill points agents at for "first move when state looks weird." It needs to actually describe what doctor does.

**Proposed body:**

```
Health check and auto-repair for meridian state.

Reconciles orphaned spawns (dead PIDs, stale heartbeats, missing
spawn directories), cleans stale session locks, and warns about
missing or malformed configuration.

Doctor is idempotent — re-running converges on the same result.
It is safe (and intended) to run after a crash, after a force-kill,
or any time `meridian spawn show` reports a status that doesn't match
reality.

Examples:
  meridian doctor                  # check and repair, JSON output
  meridian doctor --format text    # human-readable summary
```

## Gap 3 — `meridian session --help` and its subcommands are bare

Current `meridian session --help` lists `log` and `search` with one-line descriptions. Missing the principles agents need: ref types, parent inheritance, compaction segments.

**Add a one-paragraph preface** to `meridian session --help`:

```
Inspect harness session transcripts.

Session refs accept three forms: chat ids (c123), spawn ids (p123),
or raw harness session ids. By default, commands operate on
$MERIDIAN_CHAT_ID — inherited from the spawning session — so a
subagent reads its parent's transcript, not its own.
```

**Add to `meridian session log --help`:** explicit examples covering `-n`, `-c`, and `--offset`, plus the rule that `-c 0` is the latest segment and higher numbers walk backward.

**Add to `meridian session search --help`:** an example showing the navigation hint output and noting the search is case-insensitive.

## Gap 4 — `meridian work sessions --help` exists but doesn't say what it's for

Current help describes the flag (`--all`) but not the use case. Add a one-line preface:

```
List every session that has touched a work item, including
prior runs that ended before this one started. Combined with
`meridian session log`, this is the way to walk a work item's
full conversation history.
```

## Gap 5 — `meridian spawn report --help` examples are wrong

Current help on `meridian spawn report` and `meridian spawn report create` shows examples for `meridian spawn -m ... -p ...` — they were copy-pasted from the parent group and never customized. Replace with report-specific examples:

```
meridian spawn report show p107
meridian spawn report search "auth bug"
echo "Report body" | meridian spawn report create --stdin
```

## Gap 6 — `meridian spawn --help` doesn't explain `--from`

`--from` accepts a prior spawn or session ref to inherit context (report and files). Today the flag is listed with one line. Add:

```
--from REF   Inherit context from a prior spawn or session.
             Pulls in the prior spawn's report and any files it
             touched. Repeatable. Use when the new spawn needs
             the *reasoning* from a prior conversation, not just
             its artifacts.
```

## Gap 7 — `meridian mars --help` is mostly fine

`mars --help` already produces a usable command list and brief descriptions. The only addition needed is one line at the top:

```
Bundled with meridian — invoke as `meridian mars <subcommand>`
or directly as `mars <subcommand>` if installed standalone.
```

Subcommand-level help is good enough as-is. If a subcommand is missing examples, that's a mars-side improvement and can be filed separately — not a blocker for this consolidation.

## Gap 8 — `meridian config --help` is bare

Current text lists subcommands without saying what config controls. Add a preface:

```
Repository-level config (`.meridian/config.toml`) for default
agent, model, harness, timeouts, and output verbosity.

Resolved values are evaluated independently per field — a CLI
override on one field does not pull other fields from the same
source. Use `meridian config show` to see each value with its
source annotation.
```

## What Is NOT a Gap

These were considered and judged sufficient as-is:

- `meridian models list` — its output already includes routing guidance.
- `meridian work --help` — subcommand list is complete and self-explanatory.
- `meridian spawn show/list/log` — current help is sufficient for the new skill's purposes.
- `mars` subcommand-level help — adequate for the "point and learn" pattern.

## Implementation Notes for the Plan

Each gap above is a one-file edit (or small handful) in `src/meridian/cli/`. The planner should bundle them into a single phase ("expand --help text") that runs *before* the skill deletions, so an agent following an in-progress consolidation never lands on a stale help text.

Verification for that phase: run each updated `--help` and confirm the new content appears. No code tests needed — these are docstrings.
