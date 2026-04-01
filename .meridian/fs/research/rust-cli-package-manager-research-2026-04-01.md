# Rust CLI + Package Manager Architecture Research (2026-04-01)

Scope: practical architecture guidance for `mars-agents` refactor, focused on typestate, CLI layering, resolver/install pipelines, error taxonomy, atomic file operations, and module boundaries.

## 1) Rust typestate pattern

### Finding
- **Title:** The Typestate Pattern in Rust
- **URL:** https://cliffle.com/blog/rust-typestate/
- **Key takeaway:** This article frames typestate as encoding runtime state in compile-time type, so illegal operation ordering fails at compile time. It gives concrete examples where transitions consume one type and return another, removing invalid methods from the API surface after transition. This is strongest when APIs have strict phase/order semantics.
- **Directly applicable to mars-agents refactor:** **Yes**. Use typestates for phase transitions like `UnresolvedManifest -> ResolvedPlan -> FetchedArtifacts -> InstalledState` to prevent illegal step ordering.

### Finding
- **Title:** Typestate pattern in Rust
- **URL:** https://farazdagi.com/posts/2024-04-07-typestate-pattern/
- **Key takeaway:** A practical FSM-style walkthrough with explicit state structs, marker traits, transition methods, and controlled initial state construction. It also covers multi-destination transitions and shared functionality across states. The core value is expressing invariants in signatures instead of runtime checks.
- **Directly applicable to mars-agents refactor:** **Yes**. Useful for modeling lock/update/install workflows and preventing invalid transition calls at compile time.

## 2) Rust CLI architecture (separating parsing from domain logic)

### Finding
- **Title:** ripgrep `parse.rs` / `hiargs.rs` / `main.rs` architecture
- **URL:** https://raw.githubusercontent.com/BurntSushi/ripgrep/master/crates/core/flags/parse.rs
- **Key takeaway:** ripgrep has an explicit low-level parse layer (`LowArgs`) that is converted to higher-level typed args (`HiArgs`) before execution. The top-level `run` receives already-structured arguments, and command execution logic is decoupled from lexical parsing concerns. This is a clean parse/normalize/execute pipeline.
- **Directly applicable to mars-agents refactor:** **Yes**. Mirror this with `CliArgs -> ValidatedCommand -> DomainOperation`, keeping clap and raw flag details out of resolver/install core.

### Finding
- **Title:** clap 4.0, a Rust CLI argument parser
- **URL:** https://epage.github.io/blog/2022/09/clap4/
- **Key takeaway:** Maintainer write-up emphasizing long-term API maintainability and clearer derive/builder ergonomics as complexity grows. It highlights migration costs and the need for clearer attribute surfaces to reduce user confusion. Architecture implication: keep parser schema evolution manageable and avoid parser logic bleeding into app core.
- **Directly applicable to mars-agents refactor:** **Partial**. Useful as parser-layer design guidance; less about package-manager pipeline internals.

### Finding
- **Title:** Command Line Applications in Rust (In-depth topics)
- **URL:** https://rust-cli.github.io/book/in-depth/index.html
- **Key takeaway:** The in-depth track is organized around operational concerns (config, exit codes, machine/human output) rather than parser mechanics, which encourages layered CLI design. The structure itself is a good architecture cue: treat parse, configuration, output policy, and domain logic as separate modules.
- **Directly applicable to mars-agents refactor:** **Yes**. Helps define module boundaries for CLI policy vs package-management mechanism.

## 3) Building a package manager in Rust (resolve/fetch/install pipeline)

### Finding
- **Title:** Resolver internals (uv)
- **URL:** https://docs.astral.sh/uv/reference/internals/resolver/
- **Key takeaway:** uv documents a concrete prioritized PubGrub workflow: choose highest-priority undecided package, pick version with lock/install preference heuristics, add requirements, and backtrack on conflict with tracked incompatibilities. It also describes forked resolution for marker divergence and lockfile marker stabilization to keep results reproducible. This is practical guidance for real-world resolver behavior beyond textbook SAT descriptions.
- **Directly applicable to mars-agents refactor:** **Yes**. Strong model for splitting deterministic resolution core from policy heuristics and lockfile stabilization rules.

### Finding
- **Title:** Locking and syncing (uv)
- **URL:** https://docs.astral.sh/uv/concepts/projects/sync/
- **Key takeaway:** uv clearly separates lock and sync semantics, with explicit flags (`--locked`, `--frozen`, `--no-sync`) controlling whether to validate/update lock and environment. It treats lock freshness and environment sync as distinct concerns, while still supporting automatic defaults. This separation reduces hidden side effects and makes CI behavior predictable.
- **Directly applicable to mars-agents refactor:** **Yes**. Adopt explicit lock-check vs install/sync phases and strict-mode flags for deterministic automation.

### Finding
- **Title:** PubGrub Guide - Internals Overview
- **URL:** https://pubgrub-rs-guide.pages.dev/internals/overview/
- **Key takeaway:** The guide explains the solver loop as unit propagation, decision making, incompatibility generation, and conflict-driven backtracking. It’s especially useful for understanding where to insert diagnostics and explanation traces for failures. The model maps well to resolver implementations that need explainable conflict output.
- **Directly applicable to mars-agents refactor:** **Yes**. Good blueprint for resolver core and for building actionable conflict reports.

## 4) Rust CLI error handling patterns (thiserror vs anyhow, taxonomy, exit codes)

### Finding
- **Title:** anyhow README
- **URL:** https://raw.githubusercontent.com/dtolnay/anyhow/master/README.md
- **Key takeaway:** `anyhow::Error` is positioned for application code: ergonomic propagation plus context enrichment and optional backtraces. The README explicitly recommends `thiserror` for libraries that need dedicated stable error types. This is the clearest practical line in the thiserror-vs-anyhow debate.
- **Directly applicable to mars-agents refactor:** **Yes**. Use typed domain errors internally (library-like core), then convert to `anyhow` at CLI boundary for top-level reporting.

### Finding
- **Title:** thiserror README
- **URL:** https://raw.githubusercontent.com/dtolnay/thiserror/master/README.md
- **Key takeaway:** `thiserror` generates idiomatic `std::error::Error` implementations while keeping crate internals out of public API and supporting source/backtrace wiring. It’s suited for explicit error taxonomy with stable variants and rich context fields. This helps keep failure modes machine-classifiable without manual boilerplate.
- **Directly applicable to mars-agents refactor:** **Yes**. Define domain error enums per subsystem (resolve, fetch, install, lock I/O) and map them cleanly to CLI exit behavior.

### Finding
- **Title:** Exit codes (Command Line Applications in Rust)
- **URL:** https://rust-cli.github.io/book/in-depth/exit-code.html
- **Key takeaway:** Practical guidance recommends explicit exit-code policy and references BSD `sysexits` style mappings. It stresses that user messaging and process status are separate responsibilities. This is useful for designing predictable automation-facing CLI behavior.
- **Directly applicable to mars-agents refactor:** **Yes**. Define a stable error->exit-code map and keep it versioned/documented.

### Finding
- **Title:** `std::process::ExitCode`
- **URL:** https://doc.rust-lang.org/std/process/struct.ExitCode.html
- **Key takeaway:** `ExitCode` provides canonical success/failure plus controlled construction for other codes, with portability caveats. It is designed for `main` return-path semantics via `Termination`. This encourages explicit, typed exit decisions instead of ad-hoc integers.
- **Directly applicable to mars-agents refactor:** **Yes**. Use `ExitCode` at the CLI boundary and avoid scattering raw numeric codes.

## 5) Atomic filesystem operations in Rust

### Finding
- **Title:** atomic-write-file crate docs
- **URL:** https://docs.rs/atomic-write-file/latest/atomic_write_file/
- **Key takeaway:** Documents a commit-based atomic write flow: write temp file in same directory, `fsync`, then `rename`, with robust directory-descriptor handling on Unix. It emphasizes preserving old contents unless commit completes. This is a practical crash-safety pattern for config/lock updates.
- **Directly applicable to mars-agents refactor:** **Yes**. Apply for lockfile/state updates to avoid partial writes during crashes.

### Finding
- **Title:** How to write/replace files atomically? (Rust forum)
- **URL:** https://users.rust-lang.org/t/how-to-write-replace-files-atomically/42821/13
- **Key takeaway:** Highlights a real-world failure mode: rename alone is operationally atomic but may still lose durability under crash unless the temp file and directory are synced. The recommended sequence is temp-write, fsync(temp), rename, fsync(parent dir). This is the practical “what goes wrong in production” counterpart to simplified docs.
- **Directly applicable to mars-agents refactor:** **Yes**. Use durability-aware update sequence for lock/state artifacts.

## 6) uv architecture / Astral uv design

### Finding
- **Title:** Resolver internals (uv)
- **URL:** https://docs.astral.sh/uv/reference/internals/resolver/
- **Key takeaway:** uv combines PubGrub core with practical heuristics (priority ordering, lock/install preferences, targeted backtracking, marker forks). It persists fork marker decisions into lockfile for stable future resolutions. This is strong evidence that “pure solver” and “operational heuristics” should be distinct layers.
- **Directly applicable to mars-agents refactor:** **Yes**. Separate deterministic resolution engine from policy heuristics and persistence strategy.

### Finding
- **Title:** RFC: Tool package management in uv
- **URL:** https://github.com/astral-sh/uv/issues/3560
- **Key takeaway:** RFC discussion captures install-pipeline concerns (global env management, entrypoint installation strategy, upgrade semantics, conflict handling) that only appear at operational scale. It illustrates how pipeline design is as much lifecycle and UX policy as resolver theory. Issues/RFCs are useful for failure-mode-driven architecture.
- **Directly applicable to mars-agents refactor:** **Partial**. Python/tool specifics differ, but the lifecycle policy patterns transfer directly.

## 7) Cargo internals (resolver and separation of concerns)

### Finding
- **Title:** Cargo dependency resolver reference
- **URL:** https://doc.rust-lang.org/cargo/reference/resolver.html
- **Key takeaway:** The docs explicitly present resolver pseudo-code, unification heuristics, backtracking behavior, and lockfile preference rules. They describe where policy choices (pick-next-version, unification) shape outcomes. This is a practical map of resolver mechanism vs policy.
- **Directly applicable to mars-agents refactor:** **Yes**. Use this model to formalize your own resolution policy surface and deterministic defaults.

### Finding
- **Title:** Cargo resolver source (`core::resolver::mod.rs`)
- **URL:** https://raw.githubusercontent.com/rust-lang/cargo/master/src/cargo/core/resolver/mod.rs
- **Key takeaway:** The code structure separates resolver state, feature resolution, and registry querying (`RegistryQueryer`, `ResolveOpts`, `VersionPreferences`). This is concrete evidence of concern separation inside a production package manager. It shows how to keep feature-policy logic and fetch/registry mechanisms distinct.
- **Directly applicable to mars-agents refactor:** **Yes**. Strong template for modularizing resolve/fetch/config layers.

### Finding
- **Title:** From Simple to PubGrub: The Evolution of Cargo’s Resolver (RustWeek 2025)
- **URL:** https://2025.rustweek.org/schedule/wednesday/
- **Key takeaway:** The RustWeek agenda confirms dedicated deep-dive treatment of Cargo resolver evolution, suggesting the ecosystem recognizes resolver architecture as an evolving, policy-heavy subsystem. Talks like this are high-value for tradeoff and migration lessons that docs omit. Use it as a pointer for follow-up video/slides review.
- **Directly applicable to mars-agents refactor:** **Partial (pending talk materials)**. Promising for migration strategy, but details require full recording/slides.

### Finding
- **Title:** Cargo: Pillars (Rust blog)
- **URL:** https://blog.rust-lang.org/2016/05/05/cargo-pillars/
- **Key takeaway:** Cargo frames package management around shared workflows, reproducibility, and ecosystem-wide conventions, not only dependency solving. It emphasizes standardized workflows plus lock/checksum trust chain behavior. The architecture takeaway is that workflow policy is a first-class subsystem.
- **Directly applicable to mars-agents refactor:** **Yes**. Useful for deciding what belongs in “workflow orchestrator” vs core resolution mechanism.

## 8) Rust newtype pattern (benefit vs overhead)

### Finding
- **Title:** Newtype (Rust Design Patterns)
- **URL:** https://rust-unofficial.github.io/patterns/patterns/behavioural/newtype.html
- **Key takeaway:** Newtypes provide semantic distinction and API control with zero runtime cost, but introduce forwarding/boilerplate overhead. It’s best where type confusion is costly and APIs cross subsystem boundaries. This is a pragmatic rule-of-thumb source, not just a language feature explainer.
- **Directly applicable to mars-agents refactor:** **Yes**. Use newtypes for IDs/paths/versions/checksums/lock epochs to prevent accidental mixing.

### Finding
- **Title:** Effective Rust - Embrace the newtype pattern
- **URL:** https://effective-rust.com/newtype.html
- **Key takeaway:** Practical guidance includes when newtypes solve orphan-rule constraints and when trait-forwarding overhead becomes real. It also covers `#[repr(transparent)]` and derive-heavy ergonomics tradeoffs. Good decision aid for where wrappers are worth their maintenance cost.
- **Directly applicable to mars-agents refactor:** **Yes**. Helps decide which domain primitives deserve strong types vs aliases.

## 9) Separation of concerns in Rust (module boundaries, dependency inversion)

### Finding
- **Title:** rust-analyzer architecture
- **URL:** https://rust-analyzer.github.io/book/contributing/architecture.html
- **Key takeaway:** rust-analyzer explicitly documents crate-level API boundaries and architecture invariants, including strict independence constraints between layers. It demonstrates enforcing boundaries with dedicated facade crates and invariant docs rather than implicit conventions. This is a mature example of large-Rust-project modular discipline.
- **Directly applicable to mars-agents refactor:** **Yes**. Adopt explicit boundary crates/modules and write invariants for resolver, storage, and CLI layers.

### Finding
- **Title:** Cargo resolver source boundaries (`RegistryQueryer`, `ResolveOpts`, `VersionPreferences`)
- **URL:** https://raw.githubusercontent.com/rust-lang/cargo/master/src/cargo/core/resolver/mod.rs
- **Key takeaway:** Cargo’s resolver code path uses typed option/context structures and query abstractions to avoid direct coupling to transport or CLI details. This demonstrates practical dependency inversion inside a package manager core. It supports testing and policy evolution without rewriting fetch plumbing.
- **Directly applicable to mars-agents refactor:** **Yes**. Mirror with trait/adapter boundaries around registry/network and keep core deterministic.

## 10) Pipeline pattern Rust (typed transform pipelines)

### Finding
- **Title:** ripgrep parse pipeline (`LowArgs -> HiArgs -> run/search`)
- **URL:** https://raw.githubusercontent.com/BurntSushi/ripgrep/master/crates/core/flags/parse.rs
- **Key takeaway:** ripgrep’s staged conversion from raw parse state to high-level executable state is a concrete typed pipeline pattern in production. Each stage narrows ambiguity and enforces invariants before execution. This avoids carrying weakly-typed mutable argument bags through runtime.
- **Directly applicable to mars-agents refactor:** **Yes**. Implement `RawManifest -> NormalizedRequirements -> ResolvedGraph -> InstallPlan -> AppliedState` with dedicated structs.

### Finding
- **Title:** type-state-builder crate docs
- **URL:** https://docs.rs/type-state-builder/latest/type_state_builder/
- **Key takeaway:** Demonstrates generated typestate builders that prevent `build()` until required fields are set, turning constructor incompleteness into compile-time failure. It also documents tradeoffs (larger generated code, compile-time impact) in exchange for clearer correctness guarantees. This is useful for complex configuration assembly pipelines.
- **Directly applicable to mars-agents refactor:** **Partial**. Best for high-value config/build structs; may be overkill for simple internal DTOs.

### Finding
- **Title:** Builder with typestate in Rust
- **URL:** https://www.greyblake.com/blog/builder-with-typestate-in-rust/
- **Key takeaway:** Walks through evolving a standard builder into typestate-driven states to guarantee required fields before finalization. It’s practical for understanding ergonomics and failure messages consumers actually see. Useful as a lightweight pattern before introducing proc-macro dependencies.
- **Directly applicable to mars-agents refactor:** **Yes**. Good for install/resolve option builders where invalid combinations are common.

---

## Recommendations for `mars-agents` refactor (shortlist)

1. Introduce a typed phase pipeline: `InputSpec -> ResolvedGraph -> FetchPlan -> InstallPlan -> AppliedState`.
2. Keep clap parsing isolated from domain logic: parse/normalize in CLI layer, execute via typed command handlers.
3. Use `thiserror` domain enums in core; convert to `anyhow` at outer CLI boundary.
4. Define an explicit error-to-exit-code map using `ExitCode` (documented and testable).
5. Use atomic update protocol for lock/state artifacts: temp write + fsync + rename + fsync(parent).
6. Separate resolver mechanism from policy knobs (version preferences, lock preference, fork behavior).
7. Add module invariants docs (Cargo/rust-analyzer style) to enforce boundaries during future refactors.
