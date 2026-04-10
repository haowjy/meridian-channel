# Edge Cases, Failure Modes, Boundary Conditions

## Purpose

Enumerate every failure mode the v2 design must handle correctly. Each item is mirrored as a scenario file in `scenarios/` with the same ID and a concrete given/when/then + verification steps. This doc is the **authoritative source** for edge-case coverage — downstream testers read the scenario files, but the design is not complete until every item here has a corresponding scenario and every scenario is marked `verified` after implementation.

The items below are grouped by failure category. Every item carries:
- **ID** (matches scenario filename)
- **Scenario** (short description)
- **Why it matters** (which v1 finding it addresses or what new risk it guards)
- **Tester role** (which tester verifies it)

## Category A — Type and Contract Boundaries

### E1 — Adapter omits `resolve_launch_spec` override

**Scenario.** A developer adds a new harness by subclassing a base but forgets `resolve_launch_spec`.

**Expected.** Class instantiation fails with `TypeError: Can't instantiate abstract class ... with abstract method resolve_launch_spec`. Pyright also flags the subclass as unsatisfied Protocol / ABC.

**Why.** v1's `BaseSubprocessHarness.resolve_launch_spec` returns a generic `ResolvedLaunchSpec`, which is exactly what M2 documents as a booby trap. v2 removes the default. This scenario locks that in.

**Tester.** @unit-tester (pytest `NewHarness()` and assert `TypeError`).

### E2 — Caller passes a base `ResolvedLaunchSpec` to `ClaudeConnection.start`

**Scenario.** Test or caller constructs a `ResolvedLaunchSpec(prompt="hi", ...)` (base class) and passes it to `ClaudeConnection.start`.

**Expected.** Pyright error at the call site. Runtime also rejects because `ClaudeConnection.start` accepts `ClaudeLaunchSpec` and the type system catches the mismatch; if runtime execution occurs (e.g., via a `cast`), a guard at the top of `start` raises `TypeError`.

**Why.** M1 + v1 `spawn_manager.py:99` fallback. The typed contract must be unbypassable.

**Tester.** @unit-tester + @verifier (pyright step).

### E3 — Caller passes `None` as `PermissionResolver`

**Scenario.** Legacy caller does `adapter.resolve_launch_spec(params, None)` or `cast("PermissionResolver", None)`.

**Expected.** Pyright error. Any `# type: ignore` override at the site is a review block.

**Why.** H3 resolution. The two v1 cast sites must be deleted and the API must make this impossible.

**Tester.** @verifier (pyright) + grep-based audit (no `cast("PermissionResolver"` in the tree).

### E4 — `PermissionResolver` implementation lacks `.config`

**Scenario.** A new resolver class is added without a `config` property.

**Expected.** Pyright error at class definition (Protocol method missing). Runtime `isinstance(resolver, PermissionResolver)` returns False.

**Why.** L6 + H3. The Protocol promotion of `config` must be enforced.

**Tester.** @unit-tester.

### E5 — New field on `ClaudeLaunchSpec`, projection forgets it

**Scenario.** Developer adds `foo: str | None = None` to `ClaudeLaunchSpec` but doesn't update `projections/claude.py`.

**Expected.** `ImportError` when the projection module is first imported (which happens at application startup via the adapter module). Error message names the missing field and the file to update.

**Why.** H4 — D15 missing. This is the marquee guard. Every HIGH finding in p1411 is exactly what this scenario catches.

**Tester.** @unit-tester (add a fake field in a fixture, import module, expect ImportError).

### E6 — New field on `SpawnParams`, factory doesn't map it

**Scenario.** Developer adds `bar: str | None = None` to `SpawnParams` but doesn't update `_SPEC_HANDLED_FIELDS` or any `resolve_launch_spec` implementation.

**Expected.** `ImportError` when `launch_spec.py` is imported. Error message names the drift and lists the files to update.

**Why.** v1 uses `assert` which strips under `-O`. v2 uses `ImportError`.

**Tester.** @unit-tester (fake SpawnParams field, expect ImportError).

## Category B — Permission Flow

### E7 — Streaming Codex with `sandbox=read-only`

**Scenario.** User spawns a Codex streaming task with `PermissionConfig(sandbox="read-only")`.

**Expected.** `codex app-server` launch command contains `-c sandbox_mode="read-only"` (or equivalent — verified against real `codex app-server --help`). Debug trace confirms the flag reaches the Codex process. Attempting a write operation is rejected by Codex's sandbox.

**Why.** H1 — the silent security downgrade. The single most important test in the matrix.

**Tester.** @smoke-tester (launch real codex app-server, attempt write, confirm rejection).

### E8 — Streaming Codex with `approval=auto`

**Scenario.** User spawns Codex streaming with `approval=auto`.

**Expected.** JSON-RPC `requestApproval` calls are auto-accepted by the handler without prompting. Debug trace shows the approval-accept path.

**Why.** H1 side effect — the current code collapses all non-confirm modes to accept-all, which happens to be correct for `auto`/`yolo` but is structurally wrong. v2 makes it explicit.

**Tester.** @smoke-tester.

### E9 — Streaming Codex with `approval=default`

**Scenario.** User spawns Codex streaming with `approval=default`.

**Expected.** `codex app-server` runs with no explicit `approval_policy` override. Codex applies its own default (accept-all in exec mode). No Meridian-side accept logic is invoked.

**Why.** H1. v1 collapses default to accept-all at Meridian level; v2 lets the harness decide.

**Tester.** @smoke-tester.

### E10 — Streaming Codex with `approval=confirm`

**Scenario.** User spawns Codex streaming with `approval=confirm` (no interactive channel).

**Expected.** Any JSON-RPC `requestApproval` is rejected. A `HarnessEvent("warning/approvalRejected", {"reason": "confirm_mode", "method": method})` appears on the event queue **before** the JSON-RPC error response. Meridian logs a warning.

**Why.** M9 + H1. D14 specified rejection; v1 logs but doesn't emit the event.

**Tester.** @smoke-tester + @unit-tester (event queue assertion).

### E11 — Streaming Claude with parent `--allowedTools` forward

**Scenario.** `CLAUDECODE=1`. Parent's `.claude/settings.json` grants `["Read", "Bash"]`. Spawn uses `ExplicitToolsResolver(allowed_tools=("Read", "Edit"))`. Streaming runner forwards parent permissions via preflight.

**Expected.** Final command contains exactly **one** `--allowedTools` flag with the union `Read,Edit,Bash` (deduped, order-preserving). No duplicate flag, no dropped tools.

**Why.** H2 — the current streaming path emits two `--allowedTools` flags. Subprocess dedupes; streaming doesn't. v2 centralizes dedupe in the projection function.

**Tester.** @smoke-tester (command snapshot) + @unit-tester (projection unit test).

### E12 — Subprocess Claude with parent `--allowedTools` forward

**Scenario.** Identical inputs to E11 but via the subprocess runner.

**Expected.** Final command contains exactly one `--allowedTools` flag with the same deduped union. Parity with E11 is byte-identical modulo the base command prefix.

**Why.** Parity contract. Subprocess and streaming produce the same arg tail for the same spec.

**Tester.** @smoke-tester + parity test.

### E13 — REST server POST with no permission block

**Scenario.** Client POSTs `/spawns` with no permission metadata. Server default allows lenient mode.

**Expected.** Server constructs `NoOpPermissionResolver()` explicitly. Warning log is emitted at construction. Spawn runs with no permission enforcement. No `cast("PermissionResolver", None)` anywhere.

**Why.** H3 + L6. The `server.py:203` cast is deleted.

**Tester.** @smoke-tester + @unit-tester.

### E14 — `run_streaming_spawn` with caller-supplied resolver

**Scenario.** External caller invokes `run_streaming_spawn(config, params, perms=my_resolver, ...)` with `my_resolver.config.sandbox="read-only"`.

**Expected.** `my_resolver` reaches the adapter factory. The resulting `CodexLaunchSpec`'s projection emits the sandbox override on the wire. No cast-to-None, no silent swap to a default resolver.

**Why.** H3 + H1 combined.

**Tester.** @smoke-tester (Codex path) + @unit-tester.

## Category C — Spec-to-Wire Projection Completeness

### E15 — Claude spec round-trip with every field populated

**Scenario.** `ClaudeLaunchSpec` with `model`, `effort`, `agent_name`, `appended_system_prompt`, `agents_payload`, `continue_session_id`, `continue_fork=True`, `permission_resolver` with allow+deny, `extra_args=("--foo",)`, `interactive=False`.

**Expected.** Subprocess CLI and streaming CLI produce identical spec-derived args in canonical order: `--model` → `--effort` → `--agent` → `--append-system-prompt` → `--agents` → `--resume` → `--fork-session` → merged perm_flags+extra_args. Byte-equal.

**Why.** M3 (ordering) + H2 (dedupe) + completeness. The shared projection contract.

**Tester.** Parity test + @unit-tester.

### E16 — Codex spec round-trip with every permission combo

**Scenario.** 4×3 matrix of `sandbox ∈ {default, read-only, workspace-write, danger-full-access}` × `approval ∈ {default, auto, yolo, confirm}`. Run both subprocess and streaming projections.

**Expected.** Every cell produces a distinct wire format. Subprocess emits the right `--sandbox` / `--full-auto` / `--ask-for-approval` combo via `permission_resolver.resolve_flags`. Streaming emits the right `-c sandbox_mode` / `-c approval_policy` combo (or flag, post-verification). No cell collapses to accept-all silently.

**Why.** H1.

**Tester.** Parametrized @unit-tester + @smoke-tester for one representative cell per row.

### E17 — OpenCode spec with model prefix

**Scenario.** `OpenCodeLaunchSpec(model="opencode-claude-3-5-sonnet", ...)`.

**Expected.** Factory strips the `opencode-` prefix exactly once. Projection sends `claude-3-5-sonnet` via HTTP. Subprocess sends `claude-3-5-sonnet` via `--model`. No double-strip, no lingering prefix.

**Why.** Matches v1 D3 constraint; still correct under v2.

**Tester.** @unit-tester.

### E18 — OpenCode skills single-injection

**Scenario.** OpenCode spawn with `skills=("skill-a", "skill-b")`.

**Expected.** Exactly one channel delivers the skill content. Decision locked at spec construction: if `run_prompt_policy().include_skills=True`, prompt inlines skills and `spec.skills` is empty; otherwise `spec.skills` is populated and the HTTP payload carries them. Tester verifies the OpenCode server does not receive duplicate content.

**Why.** M4. Pre-decision requires smoke-testing real OpenCode HTTP API.

**Tester.** @smoke-tester (run against real `opencode serve`, inspect the session it creates).

### E19 — Codex `report_output_path` on streaming path

**Scenario.** Codex streaming spawn with `report_output_path=/tmp/report.md`.

**Expected.** Subprocess path: `-o /tmp/report.md` appears in the command. Streaming path: field is ignored, debug log emitted ("Codex streaming extracts reports from artifacts"). No error, no crash.

**Why.** M5 rationale: the field is Codex-only and streaming-unsupported. Clean documented asymmetry.

**Tester.** @unit-tester (both branches).

### E20 — `continue_fork=True` with `continue_session_id=None`

**Scenario.** Caller sets fork without session id.

**Expected.** Factory raises `ValueError("continue_fork=True requires continue_session_id")` at construction time.

**Why.** Defensive. v1 silently ignored.

**Tester.** @unit-tester.

## Category D — CLI Arg Ordering

### E21 — Claude subprocess vs streaming byte-equal arg tails

**Scenario.** Identical `ClaudeLaunchSpec`. Call `project_claude_spec_to_cli_args` with `SUBPROCESS_BASE` and `STREAMING_BASE`.

**Expected.** Positions 2+ (after `claude`) of the returned lists match modulo the base command. `subprocess_args[len(SUBPROCESS_BASE):] == streaming_args[len(STREAMING_BASE):]`.

**Why.** M3. One shared projection, one canonical order.

**Tester.** @unit-tester + parity test.

### E22 — User passes `--append-system-prompt` in extra_args

**Scenario.** `ClaudeLaunchSpec(appended_system_prompt="meridian-skill", extra_args=("--append-system-prompt", "user-prompt"))`.

**Expected.** Canonical position has Meridian's value, tail has user's value. Claude's last-wins semantics mean the user wins. Identical behavior on subprocess and streaming. A projection-time warning log is emitted when a known flag is detected in `extra_args`.

**Why.** M3 + policy clarity.

**Tester.** @unit-tester.

### E23 — `--allowedTools` merged from resolver + extra_args

**Scenario.** Covered by E11/E12 but with the specific assertion: if the resolver emits `--allowedTools A,B` and extra_args contains `--allowedTools C,D`, the merged output is exactly one flag `--allowedTools A,B,C,D` in the canonical position.

**Expected.** Exactly one `--allowedTools` flag with deduped union in positional order.

**Why.** H2 dedupe contract.

**Tester.** @unit-tester.

## Category E — Runner Shared Core

### E24 — Parity of `LaunchContext` across runners

**Scenario.** Call `prepare_launch_context(plan, ...)` twice with identical inputs.

**Expected.** Returned `LaunchContext` instances are equal. `.spec`, `.env`, `.run_params`, `.child_cwd`, `.env_overrides` compare equal.

**Why.** M6. Shared core must produce identical state regardless of caller.

**Tester.** @unit-tester.

### E25 — Parent Claude permissions forwarded identically

**Scenario.** `CLAUDECODE=1` with parent `.claude/settings.json` → `read_parent_claude_permissions` → `merge_allowed_tools_flag` (preflight fold into extra_args) → projection dedupe.

**Expected.** Subprocess runner and streaming runner produce the same child env and the same final `--allowedTools` value.

**Why.** M6 + H2.

**Tester.** @smoke-tester.

### E26 — No duplicate constants across runners

**Scenario.** Grep audit for `DEFAULT_*_SECONDS`, `DEFAULT_INFRA_EXIT_CODE`, `_BLOCKED_CHILD_ENV_VARS`, `BASE_COMMAND` tuples across `runner.py` and `streaming_runner.py`.

**Expected.** All constants live in `launch/constants.py`. No file-local redefinitions.

**Why.** M6.

**Tester.** @verifier (grep-based audit) + @refactor-reviewer.

## Category F — Environment and OS-level

### E27 — `python -O` strips nothing meaningful

**Scenario.** Run the full suite with `PYTHONOPTIMIZE=1 uv run pytest-llm`.

**Expected.** All completeness guards still fire (because they use `ImportError`, not `assert`). No test degrades.

**Why.** L1. v1 uses `assert` which strips under `-O`.

**Tester.** @verifier.

### E28 — Harness binary missing from PATH

**Scenario.** `claude` / `codex` / `opencode` binary not on PATH. Launch spawn.

**Expected.** Both runners emit the same structured error. Exit code matches. No silent fallback to `/bin/sh: claude: command not found`.

**Why.** Parity contract for error handling.

**Tester.** @smoke-tester.

### E29 — `codex app-server` rejects passthrough args

**Scenario.** Streaming Codex spawn with `extra_args=("--invalid-flag",)`.

**Expected.** Debug-level log emitted before launch: "Forwarding passthrough args to codex app-server: ['--invalid-flag']". Codex fails at server startup; the runner surfaces the failure via the existing error path.

**Why.** M7.

**Tester.** @smoke-tester.

## Category G — Type and Import Ordering

### E30 — Projection completeness check runs at import

**Scenario.** `import meridian.lib.harness.projections.claude` is executed at application startup.

**Expected.** Any spec-drift in `ClaudeLaunchSpec` → projection triggers `ImportError` at first import. The error is visible before any spawn runs.

**Why.** H4 hygiene — early detection.

**Tester.** @unit-tester.

### E31 — Circular imports

**Scenario.** Import ordering analysis of `launch_spec.py` → `adapter.py` → `projections/*.py` → `connections/*.py`.

**Expected.** No circular imports. Pyright / runtime import both succeed.

**Why.** Defensive. Generic type contracts can introduce subtle cycles.

**Tester.** @verifier.

## Category H — Event Stream / Observability

### E32 — Codex approval rejection event visible

**Scenario.** E10 inputs. Subscribe to the event queue.

**Expected.** `HarnessEvent("warning/approvalRejected", ...)` appears before the JSON-RPC error is returned. Consumer sees the event without inferring from downstream turn failures.

**Why.** M9.

**Tester.** @unit-tester + @smoke-tester.

### E33 — Debug log for passthrough args on streaming

**Scenario.** Streaming Codex / OpenCode with non-empty `extra_args`.

**Expected.** Debug-level log at the projection site listing the forwarded args.

**Why.** M7.

**Tester.** @verifier (log capture) + @unit-tester.

## Category I — Connection Protocol Conformance

### E34 — `OpenCodeConnection` inherits `HarnessConnection`

**Scenario.** `OpenCodeConnection.__bases__` includes `HarnessConnection[OpenCodeLaunchSpec]`.

**Expected.** Pyright enforces the full Protocol signature. `class OpenCodeConnection:` (no base) is a class-definition error.

**Why.** M8.

**Tester.** @unit-tester + @verifier (pyright).

### E35 — All three connections satisfy the same Protocol

**Scenario.** Run isinstance checks against the `HarnessLifecycle`, `HarnessSender`, `HarnessReceiver` Protocols for each concrete connection.

**Expected.** All three pass. Signature drift in any concrete implementation triggers pyright errors.

**Why.** Defensive. Keeps the three implementations in sync as the Protocol evolves.

**Tester.** @unit-tester.

## Scenario File Mapping

Every E-numbered item here has a corresponding file `scenarios/S<XXX>-<slug>.md` where `XXX` matches the E-number (zero-padded) and the slug matches the scenario description. The `scenarios/overview.md` maintains the master index.

Cross-audit rule: if the p1411 review report or any further investigation surfaces additional edge cases, they are added here and mirrored in `scenarios/`. The design is not complete until every flagged case has a scenario file with a tester assignment and a verification plan.
