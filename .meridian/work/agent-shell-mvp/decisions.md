# agent-shell-mvp — design phase decision log

Decisions made during the design phase. The 10 architectural inputs from `requirements.md` are not re-litigated here — see that file for the contract. Decisions captured below are the ones the design phase made on top of the contract.

## D1 — Use one canonical normalized event schema; wire docs derive from it

**Date:** 2026-04-08  
**Trigger:** Convergent BLOCKER from SOLID review and refactor review — `harness-abstraction.md`, `frontend-protocol.md`, and `event-flow.md` describe overlapping but inconsistent event vocabularies (`turnId` vs `runId`, `displayId` missing in normalized layer, `resultType` vs `resultKind`, `status:"ok"` vs `status:"done"`, 3-event vs 5-event thinking family).

**Decision:** The canonical contract is the **normalized event schema** in `harness-abstraction.md`. All other docs (`frontend-protocol.md`, `event-flow.md`, `interactive-tool-protocol.md`, `agent-loading.md`) reference and derive from it. The translator becomes a thin rename/wrap layer in V0 — no field synthesis, no lifecycle reconstruction. If the wire format needs a field the normalized layer doesn't have, the field is added to the normalized layer first.

**Why:** SOLID review BLOCKER-1 — without one canonical schema, the translator inevitably accumulates per-harness special cases, which is exactly the abstraction leak the design promises to avoid.

**Rejected alternative:** Derive the normalized layer from the wire format. Rejected because the wire format is currently shaped by frontend-v2/biomedical-mvp legacy and is not LCD across harnesses.

## D2 — Add an explicit `submit_tool_result` path to `HarnessSender`

**Date:** 2026-04-08  
**Trigger:** SOLID review BLOCKER-2 — locally executed tool results (python tool, interactive tools) need to flow back into the harness so the agent's turn can continue. The current design has the EventRouter writing Claude-specific `tool_result` NDJSON on stdin, which leaks Claude shape into the router and breaks DIP/OCP.

**Decision:** Add `HarnessSender.submit_tool_result(tool_call_id, result_payload, status)` as a first-class normalized command. Each adapter implements it harness-natively (Claude: stream-json `tool_result` frame on stdin; OpenCode: HTTP POST `/session/{id}/tool_result`). The router calls the abstract method only.

**Why:** The tool execution loop is the most important seam after the event stream itself. Leaking it breaks the abstraction at the highest-leverage spot.

## D3 — Capability flags describe **effective** behavior, not theoretical harness potential

**Date:** 2026-04-08  
**Trigger:** SOLID review MAJOR-3, refactor review #5. `ClaudeCodeAdapter.capabilities` advertises `mid_turn_injection=True`, `session_persistence=True`, etc., but `event-flow.md` and `frontend-protocol.md` document V0 as not supporting any of those.

**Decision:** Capability flags describe **what the adapter actually does in this build**. If V0 Claude adapter doesn't implement mid-turn injection, the flag is `False` regardless of whether stream-json could in principle support it. When V1 implements it, the flag flips to `True`. Frontend gates UI affordances on the effective flags.

**Rejected alternative:** Split into `protocol_supports_X` and `enabled_X`. Rejected as over-engineering; one honest flag is enough.

## D4 — `SessionContext` lives in `src/meridian/shell/session.py`; harness adapters in `src/meridian/shell/adapters/`

**Date:** 2026-04-08  
**Trigger:** Refactor review #1 — the design tree is split across `backend/`, `src/meridian/shell/`, and `src/meridian/lib/` in different docs. "New harness = one file + registration" can't hold if the home isn't decided.

**Decision:** All shell-related code lives under `src/meridian/shell/`. Specifically:
- `src/meridian/shell/session.py` — SessionContext, session lifecycle
- `src/meridian/shell/adapters/{base.py, claude_code.py, opencode.py}` — harness adapters
- `src/meridian/shell/translator.py` — wire ↔ normalized translator
- `src/meridian/shell/router.py` — EventRouter (now a thin pass-through, see D5)
- `src/meridian/shell/turn.py` — TurnOrchestrator (split from EventRouter, see D5)
- `src/meridian/shell/runtime/` — local kernel, exec service
- `src/meridian/shell/tools/` — interactive tool registry + V0 PyVista tools
- `src/meridian/shell/schemas/` — pydantic models

`src/meridian/lib/harness/` (the existing single-shot adapters) is **untouched**. The session-lived adapters are a new tree under `shell/adapters/`. They share concepts but not code.

`agent-loading.md` reuses the **existing** `compose_run_prompt`, `load_agent_profile`, `SkillRegistry` from `src/meridian/lib/agent/` — those functions stay where they are; `SessionContext` calls them from `src/meridian/shell/session.py`.

## D5 — Split `EventRouter` into router + `TurnOrchestrator` + `ToolExecutionCoordinator`

**Date:** 2026-04-08  
**Trigger:** Refactor review #2. The design says "EventRouter just routes" but the flow shows it intercepting tool calls, executing them locally, emitting display results, and feeding results back to the harness. That's three concerns.

**Decision:** Three modules:
- `router.py` — `EventRouter` is genuinely dumb: takes a normalized event, decides which sink (frontend WS, persistence, audit log) to send it to. No tool interception, no orchestration.
- `turn.py` — `TurnOrchestrator` owns one user turn's lifecycle. Receives `RunStarted` to `RunFinished`, knows the turn id, coordinates with `ToolExecutionCoordinator` when a tool call needs local execution.
- `tools/coordinator.py` — `ToolExecutionCoordinator` knows how to execute a normalized tool call (python, bash, interactive) against the runtime, capture the result, and submit it back via `HarnessSender.submit_tool_result()`.

Each is independently testable.

## D6 — Interactive tools run as subprocess invoked by `ToolExecutionCoordinator`, NOT inside the persistent kernel

**Date:** 2026-04-08  
**Trigger:** Convergent BLOCKER (alignment BLOCKER-1, feasibility High #2). `interactive-tool-protocol.md` chose subprocess; `local-execution.md` flipped to in-kernel. They contradicted.

**Decision:** Interactive tools run as **separate subprocesses** spawned by `ToolExecutionCoordinator`. Rationale:
- PyVista needs its own event loop and display surface; kernel blocking is fragile
- Cancellation is clean: `SIGTERM` the subprocess; kernel keeps state
- The kernel stays available for parallel python tools (it doesn't, in V0, but the constraint is cleaner)
- Mesh data is handed off via files in `<work-item>/.meridian/interactive_inputs/<tool_call_id>/` (the kernel writes mesh bytes there before invoking the interactive tool)
- File-based handoff matches files-as-authority discipline (Decision 9)

`local-execution.md` is updated to reflect this — its §12 contradicting recommendation is removed.

**Cost:** mesh round-trips through disk for every interactive picking call. Acceptable for V0; meshes are small enough.

## D7 — One global analysis venv at `~/.meridian/venvs/biomedical/`, managed by uv

**Date:** 2026-04-08  
**Trigger:** Feasibility review medium #4 — `local-execution.md` says one global venv, `repository-layout.md` says project-level `uv sync --extra biomedical`. Dad cannot debug which environment owns SimpleITK.

**Decision:** The biomedical analysis venv is **separate from** the meridian-channel project venv. It lives at `~/.meridian/venvs/biomedical/` (or platform equivalent), is created by `meridian shell init biomedical` on first run, and is the only venv the kernel uses. The project venv (where `meridian` itself runs) does NOT contain SimpleITK/PyVista/etc. — those are too heavy and too domain-specific to bundle into the meridian package.

This means biomedical packages are NOT in `pyproject.toml --extra biomedical`. They are in a separate manifest at `src/meridian/shell/runtime/manifests/biomedical.toml` (or similar) that `meridian shell init` reads. New domains add a new manifest file; `meridian shell init <domain>` provisions a new venv.

This also fixes refactor review #6 — biomedical specifics no longer leak into the core shell pyproject.

## D8 — V0 DICOM ingest = drag-drop into `<work-item>/data/raw/<dataset_name>/`, no presign/manifest dance

**Date:** 2026-04-08  
**Trigger:** Alignment review BLOCKER-2. Three docs disagreed on upload model.

**Decision:** V0 has **one** ingest path: a drag-drop zone in the frontend that POSTs multipart to a simple `POST /api/datasets/<name>` backend endpoint. The backend writes bytes directly to `<work-item>/data/raw/<dataset_name>/`. No presign, no finalize, no classify, no manifest. A sidebar `DatasetBrowser` component shows what's landed. The agent's `python` tool can read those files directly via `pydicom`.

`local-execution.md` §9 already documents this; `frontend-integration.md` §5.1 and `frontend-protocol.md` §10 are updated to match.

V1 may add the biomedical-mvp upload pipeline (presign/finalize/classify) if validation surfaces a need. V0 trusts the local filesystem.

## D9 — Single session per process, single tab, work item identity = process

**Date:** 2026-04-08  
**Trigger:** Alignment BLOCKER-3, refactor #4.

**Decision:** V0 session model is the simplest possible:
- `meridian shell start --work-item <name>` launches one backend bound to one work item.
- The work item directory IS the session identity. There is no separate `session_id` in V0 (a synthetic one is generated for wire compatibility but unused).
- Browser opens to the single shell. Multi-tab = same session, fan-out events to all connected sockets, last command wins. No isolation.
- WS disconnect: backend buffers events in memory for 30 seconds. Reconnect within window replays buffered events from last seen sequence number. After 30s, stale events are dropped; reconnect gets a `SESSION_RESYNC` event with current state digest.
- Server restart = session lost. V0 explicit non-goal: cross-process persistence.

To switch work items, restart the backend. `meridian shell start --work-item <other>` is a new process. This is intentional V0 simplification.

Multi-work-item routing in `frontend-integration.md` is **removed** for V0. The "left rail of work items" UI is deferred to V1.

## D10 — Claude Code init: use `--append-system-prompt` + `--mcp-config` for tools, NOT init stream-json frame

**Date:** 2026-04-08  
**Trigger:** SOLID MAJOR-4 — `agent-loading.md` and `harness-abstraction.md` described two different Claude init paths.

**Decision:** Claude Code adapter launches the subprocess with:
- `--append-system-prompt` — composed system prompt from `SessionContext`
- `--mcp-config` — JSON config file describing the tools (python, bash, etc.) the agent can call (Claude Code uses MCP for tool surfaces)
- `--permission-mode bypassPermissions` for V0 (we wrap permissions at the shell layer, not Claude's)
- `--input-format stream-json --output-format stream-json` for the bidirectional channel
- working directory = work item dir

Then the first `user` stream-json frame on stdin starts the conversation. **No** init system prompt frame (the `--append-system-prompt` flag handles it).

`agent-loading.md` is updated to describe `compose_run_prompt` output flowing into `--append-system-prompt`. `harness-abstraction.md` ClaudeCodeAdapter section is updated to match.

## D11 — Path A (vision self-feedback) is V0, just normal `python` + `show_image` + multimodal context

**Date:** 2026-04-08  
**Trigger:** Alignment MAJOR-3 — `overview.md` listed Path A under V1, `interactive-tool-protocol.md` described it as already-V0.

**Decision:** Path A IS V0. It is not a new tool or protocol — it's the agent calling the existing `python` tool to render a mesh to a PNG, then the next assistant turn includes the image in its context (Claude Code natively supports image inputs). No new shell mechanism. `overview.md` Path A claim is corrected to V0.

## D12 — Naming canonicalization

**Date:** 2026-04-08  
**Trigger:** Refactor review #5 — `mid_turn_injection` vs `supports_mid_turn_injection`, `SessionContext` reused for two concepts.

**Decision:**
- Capability flags: prefix with `supports_`. Canonical names: `supports_mid_turn_injection`, `supports_tool_approval_gating`, `supports_session_persistence`, `supports_session_resume`, `supports_session_fork`. Wire and backend match.
- Session naming: `SessionContext` = the **backend** object that bundles agent profile + skills + system prompt + tool defs + working dir. `SessionState` = the runtime state machine (started/idle/turn-active/cancelled/ended). `SessionInfo` = the wire payload sent to the frontend on `SESSION_HELLO`. Three distinct names, no overlap.
- Tool call IDs: `tool_call_id` everywhere (snake_case in JSON, `toolCallId` in TS).
- Turn IDs: `turn_id` everywhere. The legacy `runId` is renamed to `turn_id`.
- Display result kind field: `result_kind`, not `result_type` or `resultType`.

## D13 — Defer mid-turn injection to V1 in V0 build, but keep the abstract command in `HarnessSender` from day one

**Date:** 2026-04-08  
**Trigger:** Q2 from requirements + capability honesty (D3).

**Decision (recommendation to user — see synthesis report):** V0 does NOT implement mid-turn injection. `HarnessSender.inject_user_message()` exists in the abstraction (so OpenCode V1 can light it up trivially), but the V0 ClaudeCodeAdapter implementation raises `CapabilityNotSupported`. The capability flag is `False`. The frontend hides the affordance.

This is the orchestrator's **recommendation**; the user must confirm via Q2 in the synthesis report.

## D14 — Defer permission gating to V1; V0 runs with `bypassPermissions`

**Date:** 2026-04-08  
**Trigger:** Feasibility review medium #5 (approval policy mismatch in docs), Q2.

**Decision (recommendation):** V0 does NOT implement tool approval gating. The agent runs with `bypassPermissions` in Claude Code. `agent-loading.md` example profile is updated from `approval: confirm` to `approval: bypass` with a comment that V1 will add gating. Capability flag `supports_tool_approval_gating` is `False`. Frontend hides approve/deny buttons.

Recommendation; user confirms via Q2.

## D15 — Defer session persistence to V1; V0 is single-process, drop-on-restart

**Date:** 2026-04-08  
**Trigger:** Q2, alignment BLOCKER-3, capability honesty (D3).

**Decision (recommendation):** V0 has no session persistence. Restart = clean slate. `supports_session_persistence` = False. Files in the work item dir survive (that's the whole point of files-as-authority), but live conversation state does not.

Recommendation; user confirms via Q2.

## D16 — Decline to ship a no-terminal launcher in V0; document a one-line `meridian shell start` for someone-helping-Dad

**Date:** 2026-04-08  
**Trigger:** Alignment BLOCKER-4. Reviewer is correct that `meridian shell start` is terminal-first, which technically violates the customer reminder.

**Decision:** Acknowledge the gap. V0 ships `meridian shell start --work-item biomedical-yao` as the launch command. The "customer reminder" about Dad not touching a terminal is satisfied by **the developer (Jim) being the one who runs the install + launch on Dad's machine, then bookmarks the resulting localhost URL in Dad's browser**. This is acceptable for the validation phase because the user is hands-on with Dad. A real installer/launcher is V1.

The synthesis report flags this honestly: V0 is "Dad-friendly to use, developer-mediated to install." If the user disagrees and wants a launcher in V0, that's a scope addition the orchestrator surfaces.

## D17 — Don't ship Pydantic↔TypeScript codegen in V0; hand-maintained types

**Date:** 2026-04-08  
**Trigger:** Alignment MAJOR-2 — frontend-protocol.md proposes codegen + CI gating, which is V0 over-engineering for the load-bearing parts.

**Decision:** V0 maintains TS types in `frontend/src/lib/wire-types.ts` and Python types in `src/meridian/shell/schemas/wire.py` by hand. Both reference the canonical event schema in `harness-abstraction.md`. A test in the backend asserts the field names match. Codegen is V1 if drift becomes a real problem.

## D18 — Ship pre-built `frontend/dist` with releases; pnpm only required for development

**Date:** 2026-04-08  
**Trigger:** Alignment MAJOR-1, refactor review (pnpm/dist mismatch).

**Decision:** Releases (and the developer's local install on Dad's machine) ship `frontend/dist/` pre-built. `meridian shell start` serves the static bundle. `pnpm` is only required if you're doing frontend dev (`meridian shell dev`). `repository-layout.md` and `frontend-integration.md` are updated to match.

## D19 — Cut full Yjs collab editor; keep CM6 + content/formatting/paste/export, skip collab/persistence/transport/session

**Date:** 2026-04-08  
**Trigger:** Refactor review (editor scope), feasibility review (cut full editor), Q4.

**Decision:** Frontend `editor/` keeps:
- `editor/components/` — the editable surface
- `editor/content/`, `editor/formatting/`, `editor/paste/`, `editor/export/`
- `editor/title-header/`
- `editor/decorations/`, `editor/interaction/`

Cuts:
- `editor/collab/` — Yjs collab
- `editor/persistence/` — Yjs IndexedDB
- `editor/transport/` — Yjs transport
- `editor/session/` — Yjs session
- `editor/stories/` — keep in dev only, not in dist

Replace persistence with a simple `localStorage` autosave keyed on work item id. The editor renders a single markdown document that Dad uses for the results-section draft.

## D20 — Path-A vs Path-B mode is the responsibility of the agent + skill, not the shell

**Date:** 2026-04-08  
**Trigger:** Decision 10 in requirements + interactive tool framing.

**Decision:** The shell does NOT have a "Path A mode" or "Path B mode" toggle. The agent's data-analyst skill instructs it: "For each landmark detection, render the mesh, inspect your own output via vision; if confidence is low or unclear, call `pick_points_on_mesh`." This is a prompt-level decision, not a shell-level state. Keeps the shell domain-neutral (Decision 6).

The agent profile is updated to explicitly include this Path A/Path B fallback instruction.

## Findings deferred (not actioned in this design phase)

- **Feasibility critical-path risk #1 (jupyter_client + VTK stability over long sessions)**: not a design issue, an implementation/validation risk. Implementation phase will smoke-test with a 30-minute session early.
- **Feasibility critical-path risk #5 (biomedical skill corpus underspecified)**: agent-loading.md will be updated to include a richer placeholder for the biomedical-analyst skill but the actual skill content is implementation work, not design work. Flag in synthesis report.
- **Time-to-first-demo estimate**: not actionable in design; surface to user in synthesis report.

## Convergence pass changelog

- `design/harness-abstraction.md` — made the normalized schema canonical, added `submit_tool_result`, renamed capability flags to `supports_*`, moved the shell adapter home to `src/meridian/shell/`, and aligned Claude/OpenCode capability semantics with V0/V1 reality.
- `design/event-flow.md` — rewired the runtime narrative around `TurnOrchestrator` + `ToolExecutionCoordinator`, switched the flow to `turn_id` / `resultKind`, moved tool resumption to `submit_tool_result`, and simplified reconnect/session behavior to the single-process V0 model with `SESSION_RESYNC`.
- `design/frontend-protocol.md` — aligned `SESSION_HELLO` with effective V0 capabilities, added `SESSION_RESYNC`, updated tool/display wire shapes, documented simple multipart dataset ingest for V0, and replaced codegen with hand-maintained V0 wire types plus parity testing.
- `design/agent-loading.md` — moved `SessionContext` to `src/meridian/shell/session.py`, converged Claude init on `--append-system-prompt` + `--mcp-config`, changed the sample profile to `approval: bypass`, and added explicit Path A/Path B fallback guidance to the data-analyst prompt.
- `design/interactive-tool-protocol.md` — reinforced subprocess execution as the V0 model, made file handoff via `.meridian/interactive_inputs/<tool_call_id>/` explicit, renamed result envelopes to `tool_call_id`, and stated that Path A/B selection belongs in the agent prompt rather than shell state.
- `design/local-execution.md` — rewrote the runtime venv story around `~/.meridian/venvs/biomedical/` + `runtime/manifests/biomedical.toml`, removed the in-kernel interactive-tool recommendation in favor of subprocess coordination, and aligned session lifetime with the 30-second reconnect window.
- `design/repository-layout.md` — updated the shell tree to `session.py`, `adapters/`, `translator.py`, `router.py`, `turn.py`, `tools/coordinator.py`, and `runtime/manifests/`, removed biomedical heavy deps from `pyproject` extras in favor of `meridian shell init biomedical`, and switched the frontend/runtime story to ship prebuilt `frontend/dist`.
- `design/frontend-integration.md` — updated the frontend API/client story to simple dataset ingest and hand-maintained wire types, kept the CM6 drafting surface while explicitly cutting Yjs collab/persistence/transport/session paths, and aligned multi-tab/build behavior with the shared-session V0 model and prebuilt `frontend/dist`.
- `design/overview.md` — refreshed the component map to include `TurnOrchestrator` and `ToolExecutionCoordinator`, moved the biomedical runtime venv out of the project env, promoted Path A into V0, simplified V0 session scope to one process per work item, and documented the honest V0 launcher gap as developer-mediated.
