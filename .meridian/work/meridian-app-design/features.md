# Meridian App — User-Facing Features

Organized by mode. Each feature is phrased as what the user can *do*, not what the UI is. Priority labels: **P0** = ship in v1, **P1** = fast-follow, **P2** = later.

---

## Cross-mode / global

- **P0** Switch mode instantly (Sessions / Chat / Files) from any screen, keyboard or mouse.
- **P0** See at-a-glance system health in a persistent status bar: running / queued / done / failed counts, git sync, backend port.
- **P0** Pick an active work item globally; every mode respects it as default filter.
- **P0** Open a command palette (⌘K) that can: switch work item, open any session, open any file, launch a new session, run common agents.
- **P0** Light & dark theme; respects OS preference; manual override in settings.
- **P0** Git branch indicator in the top bar; click reveals commit / worktree info.
- **P1** Workspace switcher (multiple repos open in one browser profile).
- **P1** Desktop notifications when a watched session finishes or fails.
- **P2** Export a work item (sessions + artifacts + reports) as a zip or shareable read-only link.

---

## Mode: Sessions 📋

The "what's happening" dashboard.

### Discover
- **P0** See all sessions grouped by work item, with unattached sessions at the bottom.
- **P0** Filter by status (running / queued / done / failed / cancelled), work item, agent.
- **P0** Sort by most-recent-activity (default) or start time.
- **P0** Per work item, see git sync state (synced / ahead / behind / dirty / diverged) and last sync timestamp.
- **P1** Saved filter views ("my failures today", "all running opus sessions").
- **P1** Inline activity sparkline per row over the last 60 s.

### Create
- **P0** Launch a new session from a modal: pick agent, model (pre-filled from agent default, overridable), work item, prompt, reference files.
- **P0** See the resolved `meridian spawn` CLI command at the bottom of the modal, copyable.
- **P0** Drag-drop files into the modal to attach as `-f` references.
- **P1** Save spawn configs as templates (`/plan auth`, `/review-this-pr`).
- **P1** Launch many sessions at once from a single prompt (fan-out form).

### Act on a session
- **P0** Open a session in Chat mode (click a row).
- **P0** Cancel a running or queued session.
- **P0** Fork a session from any point (continue in a new chat).
- **P0** Archive done/failed sessions (hidden from default view, kept queryable).
- **P0** Open session log (transcript) in the inspector or a new chat.
- **P1** Re-run with same params, one click.

### Sync
- **P0** Per work item: one-click "sync now" (pull/push git) when ahead/behind/dirty.
- **P0** See sync status updates live as the context backend reconciles.
- **P1** Conflict resolution hand-off (open in editor or chat with a resolver agent).

---

## Mode: Chat 💬

The "talk to it" surface.

### Conversation
- **P0** Stream a live conversation with any running session (reuses existing `ThreadView`).
- **P0** Compose messages with the existing `Composer` (attachments, mentions).
- **P0** See tool calls, activity events, and final answers inline with clear affordances.
- **P0** Auto-follow new messages; click "jump to latest" when scrolled up.
- **P1** `@file` autocomplete referencing the Files tree.
- **P1** `@session p281` cross-reference to another running spawn.
- **P1** Inline code diff rendering when a message contains a patch.

### Parallel sessions
- **P0** Split the chat pane horizontally to watch 2–4 sessions side by side.
- **P0** Each column has its own Composer and inspector.
- **P0** Drag-reorder columns; close a column without affecting the session itself.
- **P0** Column layout persists per work item.
- **P1** "Follow this too" — temporarily pin a 5th session as a read-only column.

### Session ops (header)
- **P0** Cancel / fork / archive from the header.
- **P0** Copy the session's `chat_id` and `spawn_id`.
- **P0** Jump to the session's work item or attached files.
- **P1** Inline "replay" scrubber that re-plays activity at 1×/2×/10× speed.

### Inspector
- **P0** Per-message raw StreamEvents panel.
- **P0** Per-tool-call input/output JSON viewer (collapsible, searchable).
- **P0** Token accounting and cost estimate for the session.
- **P1** Diff viewer when a tool call edited files (tied to Files mode).

---

## Mode: Files 📁

The "show me the artifacts" surface.

### Browse
- **P0** Browse files in the active work item's directory.
- **P0** Browse artifacts produced by any selected session.
- **P0** Browse the repo within the configured `context_roots`.
- **P0** See git status per directory and per file (modified, added, untracked).
- **P0** Virtualized tree — handles thousands of files.

### Read
- **P0** Render markdown, JSON, images, text inline.
- **P0** Raw-text view for any file.
- **P0** Diff against HEAD, against another ref, or between two files.
- **P1** Notebook (`.ipynb`) rendering inline.
- **P1** Large-file streaming view (pagination / virtualization in content panel).

### Navigate & link
- **P0** Breadcrumb with copy-path.
- **P0** "Referenced by" — show which sessions mentioned this file (from context backend's index).
- **P0** Open in external editor via local URI scheme.
- **P1** Cross-link from a ThreadView tool call to the file it touched.

---

## Settings

- **P0** Theme, font, mode rail position (left / bottom), density (compact / comfortable).
- **P0** Configure which work items are visible (archive toggles).
- **P0** Configure context backend source (which folders are context roots).
- **P0** Configure default model routing per agent.
- **P1** Per-work-item preferences (default agent, default model).
- **P1** Keybinding customization.

---

## Out of scope for v1

- In-browser file editing.
- Multi-user collaboration / presence.
- Remote workspace mounting.
- Full-text code search across repo (leave to existing `Grep`/editor).
- Agent authoring UI (edit `.agents/`). CLI only for v1.
