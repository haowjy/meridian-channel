# Decisions

## 2026-04-19 — Consolidation

### Decision: Consolidate scattered UI designs

**What**: Merge app-session-architecture, harness-policy-ui-design, frontend-requirements, and frontend-ui-redesign into single meridian-app-design work item.

**Why**: Scattered designs led to inconsistencies and made it hard to see the full picture.

### Decision: Harness control via abstraction layer

**What**: HarnessControl protocol with per-harness implementations. Returns `ControlResult` indicating live/restart_required/unsupported.

**Why**: Each harness has different capabilities:
- Claude: slash commands as text, `/model` may not work
- Codex: rich JSON-RPC API with structured endpoints
- OpenCode: HTTP endpoints with per-message model override

### Decision: Model switch may require restart

**What**: If harness returns "not available" for `/model`, UI offers stop+resume flow.

**Why**: Can't force harness to support live model switching. But `--resume` with new model works.

### Decision: Effort toggle over 4-level slider

**What**: Two modes: Quick (fast/cheap) and Thorough (slower/better).

**Why**: Non-technical users don't understand "low/medium/high/max". Binary choice is simpler.

### Decision: Advanced settings collapsed by default

**What**: Harness, model, agent selection hidden behind "Advanced" toggle.

**Why**: Most users use defaults. Power users can access, but UI stays simple.

### Decision: Cross-harness switch = fresh start

**What**: Can't resume Claude session in Codex. Switch harness → start new session.

**Why**: Session formats are incompatible. Context carrying would be N×N conversion nightmare.

---

## Superseded

These work items are now superseded by this consolidated design:
- `app-session-architecture/` — absorbed
- `harness-policy-ui-design/` — absorbed

## 2026-04-19 — Server Model & Port

### Decision: Jupyter-like server model

**What**: Single server per machine, additive roots via CLI.

**Why**: 
- Simpler than multi-server model
- Users don't need to think about ports
- Roots persist, added via `meridian app <path>` which attaches to existing server
- Security: adding roots requires local CLI access

### Decision: Port 7676

**What**: Default port is 7676.

**Why**: 气流 (qì liú) = "energy flow" — fits Meridian (经络, energy channels) concept. Bio/organic, memorable, not commonly used.

### Decision: Dev tool first, approachable second

**What**: Primary target is developers. Non-technical collaborators should be able to use it, but don't dumb it down.

**Why**: It's a dev tool. Aesthetic should be VS Code / Cursor / Linear, not consumer app.

---

## 2026-04-19 — Frontend Layout Redesign

### Decision: Work-item-centric organization replaces repo grouping

**What**: Sessions are grouped by work items as first-class entities. Repos become background metadata.

**Why**: Work items represent the user's mental model ("what am I doing") better than repos ("where am I"). A user might have multiple work items in one repo, or work spanning repos. Work items are the organizing principle; repos are infrastructure.

**Alternatives rejected**:
- Repo grouping (original design): forces users to think in filesystem terms
- Flat chronological list: loses context for related sessions

### Decision: Activity bar + sidebar layout

**What**: VS Code-style layout with 48px icon activity bar on left, then 264px sidebar with work items.

**Why**: Familiar to dev tool users. Activity bar gives quick access to major views without eating horizontal space. Sidebar shows work context at a glance.

**Alternatives rejected**:
- Top navigation tabs: wastes vertical space, less discoverable
- Full-width sidebar: takes too much space from main content

### Decision: Multi-root file explorer via CLI + UI

**What**: Roots added via `meridian app root add <path>`, browsed in collapsible panel in UI.

**Why**: Mirrors VS Code multi-root workspaces. CLI-driven addition fits developer workflow (add roots from terminal where you already are). UI browsing supports file discovery and attachment.

**Alternatives rejected**:
- UI-only root management: requires folder picker dialog, worse UX for CLI-centric users
- Single root: doesn't support multi-project work

### Decision: Quick sessions section for unattached sessions

**What**: Sessions without work_id appear in dedicated "Quick" section, separate from work items.

**Why**: Not all sessions need to be organized. Quick exploratory sessions shouldn't require work item ceremony. Keeps work section clean while preserving access to one-offs.

### Decision: Server model abstraction layer for future swappability

**What**: Frontend abstracts server interactions through an API client layer. API shape documented to enable future cloud backend.

**Why**: Current design is local-first (Jupyter-like, single port). Future cloud version would need different auth, multi-tenancy, etc. Abstraction layer makes this possible without rewriting UI.

**Constraint discovered**: Deep local assumptions in current design (file paths, process spawning, filesystem roots) mean cloud backend would need significant server-side work. Frontend abstraction is necessary but not sufficient. See `design/server-abstraction.md` for details.
