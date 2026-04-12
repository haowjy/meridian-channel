# Phase 2: Conflict Warning Attribution and Suppression

## Round

1 (parallel with Phase 1)

## Scope

Update `/home/jimyao/gitrepos/mars-agents/src/models/mod.rs` so model alias conflict warnings name both the winning and losing dependencies, emit one warning per losing dependency, and suppress those warnings when the consumer explicitly overrides the alias in `[models]`. This phase owns diagnostics behavior and preserves warn-and-continue semantics.

## Boundaries

- Modify only `merge_model_config()` internals and tests in `src/models/mod.rs`.
- Do not change dependency ordering logic, `ResolvedGraph`, or sync helper extraction; those belong to Phase 1.
- Do not change the output schema of merged model config or `models-merged.json`.

## Touched Files and Modules

- `/home/jimyao/gitrepos/mars-agents/src/models/mod.rs`

## Claimed EARS Statement IDs

- S-WARN-1
- S-WARN-2
- S-WARN-3
- S-COMPAT-1

## Touched Refactor IDs

- None

## Dependencies

- None

## Tester Lanes

- `@verifier`: run focused build, lint, and targeted test verification for `src/models/mod.rs`.
- `@unit-tester`: pin warning behavior for two-way conflicts, three-way conflicts, and consumer override suppression.
- `@smoke-tester`: run a real `cargo run -- sync` fixture in `/home/jimyao/gitrepos/mars-agents/` and inspect emitted diagnostics to confirm warning text, count, and non-blocking behavior.

## Exit Criteria

- `merge_model_config()` tracks the winning dependency per alias and includes both winning and losing dependency names in the warning text.
- A two-dependency conflict emits one warning that recommends an explicit `[models.<alias>]` override.
- A three-or-more-way conflict emits one warning per losing dependency, each naming the winning dependency.
- Consumer `[models]` overrides suppress dependency-conflict warnings for that alias.
- Sync continues successfully after dependency conflicts; diagnostics remain warnings rather than errors.

## Verification Commands

- `cargo build`
- `cargo test models::`
- `cargo run -- sync`

## Risks to Watch

- Emitting duplicate warnings for the same loser when multiple conflict paths collapse onto one alias.
- Accidentally suppressing warnings for dependency-only conflicts instead of only for consumer-owned overrides.
- Changing warning text without keeping the structured diagnostic code stable.
