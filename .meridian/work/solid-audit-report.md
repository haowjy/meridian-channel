# SOLID Audit: meridian-channel

## 1. Executive Summary

- **Single Responsibility (S): C**
  Meridian has good package-level separation (`cli`, `ops`, `launch`, `state`, `harness`, `sync`), but several modules are still 350-900 lines and own too many reasons to change. The worst cases mix orchestration policy, parsing, I/O, lifecycle management, and presentation in the same unit.
- **Open/Closed (O): C**
  Harness adapters and file-backed stores are real extension seams, but many common changes still require editing central registries, policy tables, and command wiring. Adding a harness or CLI surface is not yet "one file plus registration" in practice.
- **Liskov Substitution (L): B**
  The main adapter implementations mostly honor the core behavior expected by callers, and the codebase does use capability flags. The weak spot is that substitution often relies on silent no-op defaults and adapter-specific semantic quirks rather than on explicit, narrow contracts.
- **Interface Segregation (I): C**
  There are useful narrow protocols such as `OutputSink`, `ArtifactStore`, and `PermissionResolver`, but `HarnessAdapter` is still too broad. Several consumers already treat parts of that interface as optional, which is a sign the abstraction is carrying unrelated concerns.
- **Dependency Inversion (D): C**
  The codebase clearly wants protocol-driven boundaries, but it still has several dependency direction leaks. The largest are ops/domain models importing CLI formatting helpers and harness code reaching into the concrete operations manifest.

Overall, the architecture is directionally strong and inspectable, but the code has not fully caught up with the design principles in `AGENTS.md` and `docs/_internal/ARCHITECTURE.md`. The project is strongest where it treats files, protocols, and adapters as boundaries; it is weakest where cross-layer convenience has been allowed back in.

## 2. Architecture Strengths

- The package split is sensible and documented. `docs/_internal/ARCHITECTURE.md` broadly matches the current code layout and gives maintainers a clear dependency model.
- State is genuinely file-authoritative. `spawn_store.py`, `session_store.py`, `artifact_store.py`, and `atomic.py` make the system inspectable and crash-tolerant.
- Harness adapters are a real seam. `claude.py`, `codex.py`, `opencode.py`, and `direct.py` encapsulate a meaningful amount of harness-specific behavior instead of scattering it everywhere.
- Narrow infrastructure protocols already exist in useful places: `OutputSink`, `ArtifactStore`, and `PermissionResolver` improve testability and keep many call sites decoupled.
- Event-sourced spawn/session tracking is a good fit for the product. JSONL stores plus reconciliation in `reaper.py` support crash-only recovery and make debugging straightforward.
- The codebase has solid targeted coverage around risky seams such as launch/session detection, harness ownership, permissions, and state reconciliation.

## 3. Findings

1. `D` | `Critical` | `src/meridian/lib/ops/catalog.py` (`CatalogModel.format_text`, `ModelsListOutput.format_text`, `SkillsQueryOutput.format_text`), `src/meridian/lib/ops/report.py` (`ReportSearchOutput.format_text`), `src/meridian/lib/ops/work.py` (`_format_spawn_rows`, `WorkListOutput.format_text`, `WorkShowOutput.format_text`), `src/meridian/lib/ops/diag.py` (`DoctorOutput.format_text`), `src/meridian/lib/ops/spawn/models.py` (multiple `format_text` methods), `src/meridian/lib/catalog/models.py` (`AliasEntry.format_text`)
   Issue: feature and catalog models import `meridian.cli.format_helpers` directly. That makes ops/domain code depend on a concrete surface concern, contradicts the documented layering rule, and makes non-CLI surfaces inherit CLI presentation choices.
   Suggestion: move text rendering into CLI presenter modules or an output-format registry keyed by output type. Ops/domain should return plain data only.

2. `D` | `High` | `src/meridian/lib/harness/direct.py` (`DirectAdapter.build_tool_definitions`, `_operation_by_mcp_name`, `_invoke_operation_tool`)
   Issue: a harness-layer class depends directly on `meridian.lib.ops.manifest` and concrete operation metadata. That inverts the intended dependency direction and makes the harness package aware of high-level business operations.
   Suggestion: inject a tool registry or operation gateway into `DirectAdapter`, or move the direct tool-loop orchestration to a surface/service layer above `lib/harness`.

3. `S` | `High` | `src/meridian/lib/ops/spawn/prepare.py` (`build_create_payload`)
   Issue: one function validates models, resolves runtime/config, loads agent profiles, resolves skills, routes harnesses, loads references, composes prompts, resolves continuation behavior, builds permission policy, and previews the harness command. That is too many reasons to change for one unit.
   Suggestion: split it into a small pipeline such as model/profile resolution, prompt assembly, continuation resolution, and permission/command planning.

4. `S` | `High` | `src/meridian/lib/launch/runner.py` (`spawn_and_stream`, `execute_with_finalization`)
   Issue: the launch runner owns subprocess creation, stdout/stderr capture, timeout handling, signal forwarding, retry policy, budget enforcement, watchdog behavior, artifact persistence, extraction, guardrails, and final state resolution.
   Suggestion: separate launch planning, attempt execution, retry policy, and finalization into smaller services with narrow inputs and outputs.

5. `S` | `High` | `src/meridian/cli/main.py`
   Issue: the root CLI module handles global option parsing, sink lifecycle, root help behavior, command tree construction, continuation resolution, completion installation, startup cleanup, and primary launch orchestration. It is effectively several modules fused together.
   Suggestion: extract global option handling, root-command bootstrapping, continuation resolution, and primary-launch entry into separate modules.

6. `O` | `High` | `src/meridian/lib/ops/manifest.py` (`_OPERATIONS`)
   Issue: every new operation must be imported and declared in one large central tuple. That creates a high-friction hotspot and forces extension through modification of a single file with broad knowledge of the entire system.
   Suggestion: move to module-local operation specs with package-level discovery, or keep per-domain manifests that compose into the final registry.

7. `O` | `High` | `src/meridian/cli/main.py` (`spawn_app`, `report_app`, `work_app`, `agents_app`, `skills_app`, `models_app`, `config_app`, `sync_app`, `_register_group_commands`), plus each `register_*_commands()` module
   Issue: adding a CLI group still requires editing `cli/main.py`, creating a new `App`, wiring it into the root app, and writing a per-group handler map. The manifest reduces duplication but does not eliminate the need for multiple coordinated edits.
   Suggestion: let CLI groups self-register from module metadata, or define a single group descriptor that includes the `App` construction and command registration policy.

8. `O` | `High` | `src/meridian/lib/harness/adapter.py` (`run_prompt_policy`, `filter_launch_content`), `src/meridian/lib/ops/spawn/prepare.py`, `src/meridian/lib/launch/command.py`
   Issue: harness prompt policy is split across two adapter hooks and two separate call paths for child and primary launches. A new harness or prompt rule has to be threaded through multiple locations.
   Suggestion: replace the current pair of hooks with one adapter-owned prompt-plan object consumed uniformly by both primary and child launch flows.

9. `S` | `High` | `src/meridian/lib/catalog/models.py`
   Issue: this module combines model-family routing, external fetches, cache TTL handling, payload normalization, alias merging, visibility heuristics, and text formatting. It is a good example of package-level intent collapsing into file-level sprawl.
   Suggestion: split it into `routing.py`, `discovery.py`, `cache.py`, `aliases.py`, and `catalog_view.py` or equivalent focused modules.

10. `I` | `Medium` | `src/meridian/lib/harness/adapter.py` (`HarnessAdapter`, `BaseHarnessAdapter`, `resolve_mcp_config`), `src/meridian/lib/launch/env.py` (`build_harness_child_env`)
    Issue: `HarnessAdapter` is carrying too many unrelated responsibilities: command building, environment overrides, MCP wiring, prompt policy, stream parsing, usage extraction, session handling, task extraction, findings extraction, summary extraction, and more. Consumers already use `getattr` and default no-ops because not all adapters actually support all parts.
    Suggestion: split the adapter contract into smaller capability-specific protocols or strategy objects, and make unsupported capabilities explicit in types rather than implicit at runtime.

11. `O` | `Medium` | `src/meridian/lib/catalog/models.py` (`route_model`, `_PROVIDER_TO_HARNESS`), `src/meridian/lib/harness/registry.py` (`with_defaults`), `src/meridian/lib/safety/permissions.py` (`permission_flags_for_harness`), `src/meridian/lib/harness/materialize.py`
    Issue: harness-specific policy is spread across several central modules. Adding a new harness means touching adapter registration, model routing, permission translation, and often materialization behavior.
    Suggestion: move harness-owned policy into the adapter or adapter metadata so central code only composes registered adapters rather than pattern-matching on harness IDs.

12. `S` | `Medium` | `src/meridian/lib/sync/engine.py`
    Issue: the sync engine handles source resolution, discovery, collision detection, staging, hashing, install/update decisions, Claude symlink behavior, pruning, orphan warnings, and lock-file updates in one module. It is doing orchestration, policy, and filesystem mutation together.
    Suggestion: separate discovery/diffing from apply/prune execution, and isolate harness-specific filesystem quirks into dedicated helpers or strategies.

13. `S` | `Medium` | `src/meridian/lib/launch/resolve.py` (`resolve_primary_session_metadata`) and `src/meridian/lib/launch/command.py` (`build_harness_context`)
    Issue: primary launch resolution is duplicated. Both paths re-resolve profile defaults, harness selection, skills, and related metadata, which makes future rule changes easy to apply inconsistently.
    Suggestion: introduce one immutable `ResolvedPrimaryLaunch` object and feed both dry-run and execution paths from that shared resolution step.

14. `S` | `Medium` | `src/meridian/lib/launch/process.py` (`run_harness_process`)
    Issue: the primary process runner still mixes session lifecycle, spawn-store updates, command/env assembly, artifact copying, session ID reconciliation, lock management, and materialization cleanup. Helper extraction has started, but the orchestration boundary is still too broad.
    Suggestion: split "primary session lifecycle management" from "interactive process execution" so each can evolve independently.

15. `D` | `Low` | `src/meridian/lib/ops/runtime.py` (`OperationRuntime.harness_registry: Any`)
    Issue: the runtime bundle erases the harness registry contract to avoid a circular import. That makes the dependency less explicit and weakens static guarantees at a boundary that should be strongly typed.
    Suggestion: define a narrow registry protocol in a lower-level module and depend on that protocol instead of `Any`.

16. `D` | `Medium` | `src/meridian/cli/sync_cmd.py`
    Issue: the sync CLI is not a thin surface. It performs config I/O, lock handling, hashing, deletion behavior, and payload shaping directly instead of delegating through typed ops-layer commands like the rest of the system.
    Suggestion: add a dedicated `lib/ops/sync.py` and make `cli/sync_cmd.py` a thin argument-mapping layer, consistent with the architecture used for spawn, report, work, and catalog operations.

## 4. Extensibility Scorecard

- **Add harness: Moderate**
  The adapter seam is real, but a new harness still requires edits in adapter registration, model routing, permission translation, and sometimes materialization behavior.
- **Add CLI group: Hard**
  You need a new CLI module, a new `App` in `cli/main.py`, root registration, and often manual handler maps even when the operation manifest already exists.
- **Add spawn state: Moderate**
  The event-store model is straightforward to extend, but derived projections, query helpers, reconciliation, and presentation layers all need to stay in sync.
- **Add output format: Hard**
  `create_sink()` is small, but text formatting is distributed across many output models and imports CLI helpers directly, so presentation is not centralized.
- **Add catalog entity: Moderate**
  There are patterns to copy from agents/skills/models, but each entity currently has bespoke discovery, ops, and CLI wiring rather than a common catalog framework.

## 5. Top 5 Refactoring Priorities

1. **Move all text formatting out of ops/domain models**
   This has the best impact-to-effort ratio because it fixes a real layer violation and makes future output formats dramatically easier.
2. **Introduce a single resolved launch plan shared by primary and child launches**
   This would remove duplicated resolution logic and create a cleaner seam between policy and execution.
3. **Split `HarnessAdapter` into smaller capability interfaces**
   That would improve substitutability, remove no-op contracts, and localize harness-specific behavior more cleanly.
4. **Break the central operation and CLI registration hotspots into composable manifests**
   This is the main step needed to make "extend, don’t modify" true for commands and surfaces.
5. **Decompose large policy-heavy modules (`catalog/models.py`, `config/settings.py`, `sync/engine.py`, `launch/runner.py`)**
   These files are where most change amplification will continue to accumulate if left as-is.
