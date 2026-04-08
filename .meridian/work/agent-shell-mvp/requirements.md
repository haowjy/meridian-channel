# Agent Shell MVP — Requirements

> Materialized from conversation `c1046` on 2026-04-08. This document is the
> source of truth for the design phase. The conversation is the history; this
> doc is the contract. Read this first; mine the parent session only for nuance
> on specific decisions.

## Vision

Build a **domain-flexible agent shell** that runs locally on a user's machine, wraps a Claude Code (and eventually Codex / opencode) subprocess as the conductor, and provides a polished web UI for end users to interact with the agent. The shell is generic; **domain specialization happens through agent profiles, skills, and on-demand interactive tools — never through hardcoded shell behavior.**

The first validation domain is **biomedical (μCT analysis for the Yao Lab at University of Rochester, musculoskeletal research)**, but the user is explicit that biomedical may not be the long-term domain. Whatever ships must be domain-pivot-friendly: swap the agent profile, swap the interactive tools, keep everything else.

This is the amalgamation of three existing efforts:

1. **meridian-channel** (this repo) — its agent profile system, skill loading, harness adapter pattern, work item lifecycle, mars sync, files-as-authority, decision logs.
2. **meridian-flow biomedical-mvp pivot** (`../meridian-flow/.meridian/work/biomedical-mvp/`) — the biomedical pivot design, WebSocket contract evolution, ActivityBlock model, result capture protocol, 3D viewer model, dataset upload model.
3. **meridian-flow frontend-v2** (`../meridian-flow/frontend-v2/`) — the React 19 + Tailwind v4 frontend originally built for an AI-writing-assistant product, then extended in the biomedical pivot. Has UI atoms, AG-UI activity stream reducer, WebSocket client, thread components, editor (CM6+Yjs).

## Validation goal

Reproduce the Yao Lab μCT paper pipeline end-to-end with one agent profile + one skill set:

1. Load DICOM stacks from Scanco VivaCT 40
2. Preprocess/clean raw voxel data
3. Segment femur, tibia, patella, osteophytes via threshold + watershed
4. Show 3D model in viewer for researcher validation
5. Correct orientation (PCA-based auto-alignment)
6. **Detect anatomical landmarks automatically** — critical step; this is where most of analysis time goes today
7. Extract geometric indices (femoral W/L ratio, tibial IIOC H/W ratio)
8. Run ANOVA with Dunnett's post hoc, ROC curves, Bland-Altman, ICC
9. Generate publication-quality figures
10. Draft results section text

The validation customer is "Dad" (Yao Lab researcher). He must be able to use this without touching a terminal — **a real UI is required from V0**, not deferrable.

## Key architectural decisions made in conversation

These are not up for re-debate in design. They are inputs.

### Decision 1: Amalgamation lives in meridian-channel
The new shell lives in this repo (meridian-channel), not meridian-flow. frontend-v2 gets **copied into this repo**, not symlinked or cross-referenced. meridian-channel grows from "Python CLI for dev orchestration" into "Python CLI + Python backend + React frontend, full agent shell platform." The Go backend in meridian-flow is **not part of V0** (no auth, no Supabase, no Daytona, no billing). It may be revisited post-validation.

### Decision 2: Python FastAPI backend with WebSocket
- New Python backend, FastAPI + WebSocket
- Translates between two protocol surfaces:
  - **Frontend side**: speaks the frontend-v2 WebSocket contract (the AG-UI / activity stream protocol that was being designed in biomedical-mvp pivot — design must read what already exists there)
  - **Harness side**: speaks each harness's own protocol (Claude Code stream-json subprocess, opencode HTTP/ACP, codex TBD)
- All local. No cloud. No auth. Single user. Local files.
- Reuses meridian-channel's existing `.agents/` loading machinery so the data-analyst agent profile + biomedical skills are managed through mars sync, not hand-written into the backend.

### Decision 3: Harness abstraction must be SOLID-compliant — explicit DIP, OCP, ISP
The user invoked SOLID explicitly. This is a load-bearing requirement, not a nice-to-have:

- **SRP** — `HarnessAdapter` knows how to lifecycle one specific harness. `FrontendTranslator` knows the frontend contract. `EventRouter` maps between them. Three separate concerns, three separate modules.
- **OCP** — adding a new harness = adding a new adapter file + registration. Zero modifications to router or translator. The interface must be a least-common-denominator that doesn't lose information from any harness — designed against opencode's HTTP/ACP shape, not warped to Claude Code's stream-json shape (the user explicitly noted opencode is "easier because designed in a modular way").
- **ISP** — split the harness interface so consumers see only what they need. Likely shape: `HarnessLifecycle` (start/stop/health), `HarnessSender` (user message, interrupt, approve tool), `HarnessReceiver` (event stream out).
- **LSP** — adapters are interchangeable; swapping Claude Code for opencode is a config change, not a code change.
- **DIP** — FastAPI depends on the abstract `HarnessAdapter`, not on `ClaudeCodeAdapter`.

The new harness adapters are conceptually descended from meridian-channel's existing single-shot adapters in `src/meridian/lib/harness/`, but they are **session-lived** (long-running subprocess, bidirectional streaming) instead of fire-and-forget. The existing pattern informs the new one but does not bind it.

### Decision 4: V0 is Claude Code only, V1 adds opencode
- V0 ships with `ClaudeCodeAdapter` only.
- V1 adds `OpenCodeAdapter` (opencode is the priority second adapter because of its modular HTTP/ACP design).
- Codex headless integration is deferred indefinitely — Codex's `exec` mode is single-shot, no mid-turn injection support, so it doesn't fit the long-lived session model. Codex is documented as "TBD" in the abstraction but no implementation in V0 or V1.

### Decision 5: Frontend is frontend-v2 copied into this repo
Not Reflex, not Streamlit, not Gradio, not a fresh React app. The user already has frontend-v2 from the writing-app + biomedical-pivot history. It has the activity stream reducer, WebSocket client, thread components, UI atoms — most of the hard parts. The missing pieces (layouts, routes, stores, API client) were already on the biomed-mvp roadmap. Copy frontend-v2 into this repo, complete the missing pieces, point the API client at the new Python backend.

### Decision 6: Domain extension is interactive tools, not panels
Domain-specific UX is delivered through **interactive Python tools the agent calls**, not through custom UI panels in the shell. Example: when the agent needs landmark coordinates and can't determine them autonomously, it calls a `pick_points_on_mesh()` tool, which opens a **standalone PyVista window** with rotate/zoom/pick widgets, the user clicks landmarks, the window closes, the tool returns coordinates as JSON, the agent continues.

This means:
- The shell renders chat + tool timeline + inline images. Generic.
- Each domain ships: agent profile + skills + interactive tools.
- Biomedical V0 ships: data-analyst agent + biomedical skills + interactive PyVista tool(s) (point pick, box select, region pick).
- Pivoting domain is "swap the agent + skills + tools," not "rebuild the shell."

PyVista has built-in support for `enable_point_picking()`, `enable_cell_picking()`, `add_box_widget()`, `add_sphere_widget()`, multi-mesh scenes, OrbitControls. The interactive tool wraps these as a callable subprocess that blocks until the user closes the window.

### Decision 7: Local Python venv is the analysis runtime
- User installs Python + uv as a prerequisite (acceptable because Python is required for analysis anyway)
- Biomedical packages: SimpleITK, scipy, numpy, pandas, scikit-image, plotly, matplotlib, pydicom, trimesh, PyVista
- The agent's `python` and `bash` tools execute against this local venv
- Persistent kernel across tool calls (matches the biomed-mvp result_helper protocol)
- **Not Daytona for V0.** Daytona is deferred. Single-user local execution is the V0 model.

### Decision 8: meridian-channel stays in Python; rewrite explicitly deferred
The user raised the question of rewriting meridian-channel out of Python and we deferred it explicitly. **The Python implementation is the substrate. Do not rewrite it. Do not propose rewriting it.** The rewrite question may be revisited after validation produces evidence that Python is the constraint. Until then it is parked.

### Decision 9: Files-as-authority extends to scientific reproducibility
Meridian-channel's files-as-authority discipline maps perfectly onto scientific audit trails. Every analysis step's inputs, outputs, and decisions land as files under the work item directory. The decision log doubles as a methods section. This is a feature, not an accident — design should preserve and amplify it.

### Decision 10: Validation pivot — autonomous → co-pilot with feedback loops
The user ran a prototype attempt and discovered that the model cannot do biomedical analysis blind. It needs **either** agent self-feedback via vision (off-screen rendering + multimodal inspection of its own output, "Path A") **or** human-in-the-loop interactive correction via the PyVista tool ("Path B"), or both. The original requirements doc framing of "autonomous end-to-end" is **superseded**: the actual product is **co-pilot with feedback loops**, where Path A handles routine validation and Path B handles cases the agent can't resolve alone. Design must support both.

## Open questions for the design phase to resolve

The design-orchestrator should surface these to the user and get answers before committing to a final design.

### Q1: Replace, coexist, or replace-eventually for meridian-flow?
Three possibilities and the discipline differs:
- **(a) Replace** — meridian-flow Go backend sunsets. Amalgamation IS the new product.
- **(b) Coexist** — Amalgamation is V0 prototype; meridian-flow stays as long-term product; reconverge later.
- **(c) Replace eventually** — Amalgamation is the new path. Meridian-flow runs in parallel until the amalgamation has feature parity, then meridian-flow deprecates.

The user leans (c) but has not committed. This affects how much design quality this V0 deserves: throwaway prototype optimizes for speed, replacement product invests in design.

### Q2: V0 scope on three optional features
Each adds non-trivial implementation cost. The design must explicitly decide V0/V1/deferred for each:

- **Mid-turn injection.** Send a user message into a running session mid-tool-call by writing stream-json to Claude Code's stdin. This was the user's original interest at the top of the conversation. Opencode supports it via HTTP; Claude Code supports it via stream-json on stdin. Implementing it in V0 means the backend must hold the subprocess stdin open and have a clean protocol for "interrupt the agent." Default position: V1, but the user may want V0 if Dad will need to course-correct mid-analysis.
- **Permission gating.** Companion has this — agent asks for approval before sensitive operations, user approves/denies in the UI. Default position: V1. User has not pushed for V0.
- **Session persistence and resume.** Server restart doesn't lose conversation state. Default position: V1. V0 is single-session-per-process.

### Q3: Repository layout
Where in meridian-channel does the new code live? Suggested defaults to push back on:
- `backend/` — new Python FastAPI service (separate from `src/meridian/`)
- `frontend/` — React frontend-v2 copy
- The shell becomes a new meridian subcommand: `meridian shell start` launches backend + frontend + harness
- Or the shell is an entirely separate binary/script and meridian CLI stays as the dev tool

The design must pick one and justify it. Affects mars sync, `uv sync`, CI, install path.

### Q4: What from frontend-v2 stays vs. gets cut
frontend-v2 contains writing-app legacy components (editor with CM6+Yjs, document tree) that may or may not be useful for biomedical/general agent shell:
- **Editor (CM6+Yjs):** useful if the agent drafts paper sections (it does, in step 10 of validation). Probably stays.
- **Document tree:** not obviously relevant to biomedical analysis. Probably cut.
- **Thread components:** essential, stay.
- **AG-UI activity stream:** essential, stay.
- **WebSocket client:** essential, stay (but extended/replaced for the new Python backend protocol).
- **UI atoms:** essential, stay.

Design must enumerate and decide.

### Q5: Mid-turn injection priority for opencode vs. Claude Code
Even if mid-turn injection is V1, the harness abstraction designed in V0 must accommodate it. Opencode's HTTP model makes mid-turn injection trivial (POST another message). Claude Code's stream-json on stdin works but is poorly documented. Design the abstraction so the simpler interface (opencode) doesn't get warped by the harder one (Claude Code).

## SOLID requirements applied to specific design surfaces

The user said "SOLID" explicitly. Surfaces where this is most load-bearing:

### Harness abstraction
See Decision 3 above. Get this wrong and adding opencode requires a backend rewrite.

### Frontend protocol translator
- Translator is a separate concern from the harness abstraction. Translator knows "frontend says X, that means harness command Y." Harness knows "send this command to my subprocess."
- Adding a new frontend protocol (e.g. a different chat client) = new translator, no harness changes.
- Adding a new harness = new adapter, no translator changes.

### Activity stream
The biomedical-mvp pivot defined an `ActivityBlock` model with per-tool-category collapse defaults. This is already SOLID-aligned (each tool category registers its own display config). Design should preserve this and not bake biomedical-specific tool categories into the shell.

### Interactive tool protocol
- Tools register themselves as agent-callable (via `.agents/skills` or similar)
- The shell does not know about specific tools (PyVista, anything else)
- A new domain ships new tools without modifying the shell

## What the design must NOT do

- Do not propose rewriting meridian-channel out of Python.
- Do not bake biomedical-specific behavior into the shell, the backend, or the protocol.
- Do not require the Go backend to participate in V0.
- Do not require Daytona, Supabase, auth, or billing in V0.
- Do not design around `companion` (the TypeScript reference implementation). Companion is reference material the user pointed at; the design is its own thing in Python. The team should still read companion to understand the stream-json protocol.
- Do not over-engineer. The user's repeated discipline is rapid prototype, validate, defer infrastructure. Design quality is for the load-bearing parts (harness abstraction, protocol translator, agent loading) — not for every component.

## Reference paths the design phase must read

These are inputs the design-orchestrator's grounding phase (via @explorers) must mine:

1. **biomedical-mvp work item in meridian-flow:**
   - `../meridian-flow/.meridian/work/biomedical-mvp/requirements.md`
   - `../meridian-flow/.meridian/work/biomedical-mvp/design/overview.md`
   - `../meridian-flow/.meridian/work/biomedical-mvp/design/agent/`
   - `../meridian-flow/.meridian/work/biomedical-mvp/design/backend/`
   - `../meridian-flow/.meridian/work/biomedical-mvp/design/frontend/`
   - `../meridian-flow/.meridian/work/biomedical-mvp/design/upload-pipeline/`
   - `../meridian-flow/.meridian/work/biomedical-mvp/design/streaming-walkthrough.md`
   - `../meridian-flow/.meridian/work/biomedical-mvp/briefs/`
   - `../meridian-flow/.meridian/work/biomedical-mvp/decisions.md`
   - `../meridian-flow/.meridian/work/biomedical-mvp/plan/`

2. **frontend-v2 in meridian-flow:**
   - `../meridian-flow/frontend-v2/` (full structure)
   - Specifically: AG-UI activity stream reducer, WebSocket client, thread components, UI atoms, what protocol the WebSocket client expects

3. **meridian-channel itself (this repo):**
   - `src/meridian/lib/harness/` — existing single-shot harness adapter pattern; the new long-lived adapters descend conceptually from this
   - How `.agents/` flows from mars sync into a Claude Code session at spawn time
   - The agent profile + skill loading mechanism

4. **Companion as protocol reference (read, don't fork):**
   - https://github.com/The-Vibe-Company/companion — TypeScript reference for how to bridge Claude Code stream-json to a WebSocket frontend. Read for protocol understanding only. The Python backend is its own implementation.

## Suggested design split (orchestrator may adjust)

The design phase should produce these documents (one architect per area, parallel where independent):

1. **`design/overview.md`** — system topology, component map, data flow diagram
2. **`design/harness-abstraction.md`** — `HarnessAdapter` interface, lifecycle/sender/receiver split, Claude Code adapter mechanics, opencode adapter sketch (V1 placeholder), how the abstraction stays neutral to both
3. **`design/event-flow.md`** — message lifecycle from user input through frontend → translator → harness → tool execution → results back to frontend; includes the mid-turn injection design (even if V1)
4. **`design/frontend-protocol.md`** — the WebSocket contract between frontend-v2 and the Python backend; must mine the existing biomed-mvp pivot WebSocket contract and either adopt it as-is or evolve it with explicit rationale
5. **`design/agent-loading.md`** — how meridian-channel's `.agents/` system surfaces agent profiles + skills + system prompt injections to a Claude Code subprocess at session start (and how this stays clean for opencode later)
6. **`design/interactive-tool-protocol.md`** — how the agent calls a blocking interactive tool (e.g. PyVista point picker), how the tool returns structured results, how this scales to non-PyVista tools in other domains
7. **`design/repository-layout.md`** — where new code lives in meridian-channel, how the shell relates to the existing CLI, what gets installed by `uv sync`, what ships in `mars sync`, how the user launches the shell (`meridian shell start` vs separate binary)
8. **`design/frontend-integration.md`** — frontend-v2 copy strategy, what stays / cuts / extends, how the missing layouts/routes/stores/API client get filled in, how biomedical-mvp pivot designs map onto them
9. **`design/local-execution.md`** — Python venv model, how the agent's python/bash tools resolve to the local environment, how the persistent kernel works, how interactive tools coordinate with the analysis venv

These can run as parallel @architect spawns where independent. Order of dependence:
- (1) overview is first; everything else slots into it
- (2)+(3)+(5) form the backend core; (2) is the most load-bearing
- (4) depends on (3) and on grounding from biomed-mvp pivot
- (8) depends on (4)
- (6)+(9) are mostly independent
- (7) is mostly independent

After all areas have first-pass designs, run a final fan-out review across diverse models with refactor-reviewer included, per `agent-staffing` skill.

## Customer reminder

This is for **Dad** at Yao Lab. He is a real human being, the first user, the validation customer. He uses Amira today and it has a one-year learning curve. The MVP is "good enough to do his actual μCT pipeline on his actual data without fighting the tool." Every design decision should be checkable against "would this make Dad's life better."
