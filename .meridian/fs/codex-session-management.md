# Codex CLI Session Management: Research Report

Date: 2026-03-29

## Summary

Codex CLI has first-class session continuity, a native `codex fork` command, and a well-defined local storage format. There is no `--continue` flag in the traditional sense, but `codex resume --last` and `codex resume <SESSION_ID>` cover that use case. Forking is a first-class operation. Sessions are identified by UUID v7. Session IDs cannot be injected at launch time (an open feature request as of the research date).

---

## 1. Session Continuity: How It Works

Codex has two continuation mechanisms:

**`codex resume`** — continues a session *within the same thread*. Replays the persisted event history and appends new activity to the same rollout file.

- `codex resume` — opens an interactive picker of recent sessions
- `codex resume --last` — skips the picker; resumes the most recent session from the current working directory
- `codex resume <SESSION_ID>` — resumes a specific session by UUID
- `codex resume --all` — includes sessions from all working directories (not just cwd)
- `codex exec resume --last "new prompt"` — non-interactive variant for automation

**`/resume`** slash command — available inside an active session, opens the picker inline.

There is no `--continue` flag. The `codex resume --last` pattern is the equivalent.

**Model mismatch handling**: if you resume a session with a different model configured, Codex emits a warning event but still proceeds.

---

## 2. Session Storage

### Location

```
~/.codex/sessions/YYYY/MM/DD/
```

Or `$CODEX_HOME/sessions/YYYY/MM/DD/` if `CODEX_HOME` is set.

### File format

Files are named `rollout-<UUID>.jsonl` (or `.jsonl.zst` when compressed with zstandard). They are JSONL event logs containing the complete sequence of turns, tool calls, command outputs, and context data.

Command outputs are truncated to 10,000 bytes per aggregated output in the stored file to prevent bloat (configurable via `PERSISTED_EXEC_AGGREGATED_OUTPUT_MAX_BYTES`).

### Metadata index

A SQLite state database lives alongside the rollout files. It stores `ThreadMetadata` (summary info: cwd, git branch, first message) for fast listing and searching without parsing every JSONL file.

### Session ID embedded in file

The session UUID is stored *inside* the JSONL file, not just in the filename. Renaming the file does not change the internal ID. The resume function uses the internal ID.

---

## 3. Session Identification

Sessions use **UUID v7** (`ThreadId`). These are auto-generated at session start. As of the research date, there is no supported way to inject a session ID at launch — Codex always generates one internally. A feature request for `--session-id <uuid>` (issue #13242) exists but is unimplemented.

You can discover the session ID via:
- The interactive picker (copy from UI)
- `/status` slash command inside an active session
- Scanning `~/.codex/sessions/` for the filename

---

## 4. Fork Capability

Fork is a **first-class, native operation** in Codex CLI.

### Top-level command

```
codex fork                    # opens session picker, forks selected session
codex fork --last             # forks the most recent session
codex fork <SESSION_ID>       # forks a specific session
codex fork --all              # include sessions beyond current cwd in picker
```

### Slash command (within active session)

`/fork` — clones the current conversation into a new thread with a fresh UUID, leaving the original untouched.

### Keyboard shortcut

Press Escape twice with an empty composer to enter backtrack mode. Continue pressing Escape to walk back through the transcript. Press Enter to fork from that earlier point. This is the mechanism for mid-conversation branching at a specific turn.

### What fork does internally

1. Locates the parent rollout file by session ID
2. Generates a new UUID v7 (`ThreadId`)
3. Initializes a `RolloutRecorder` with `forked_from_id` set to the parent ID (parentage is tracked in metadata)
4. Populates the new thread's initial history from the parent's event sequence
5. Launches the interactive interface with the forked data loaded

The parent session is **completely unmodified**. The fork is an independent copy with its own thread ID.

### SDK fork (not implemented)

Issue #4972 requested exposing `ConversationManager::fork_conversation` in the TypeScript SDK. The issue was closed as "COMPLETED" in October 2025, but no referenced commit or API surface was identified. Treat SDK-level fork access as unverified.

---

## 5. Manual Fork by Copying Session Files

This is theoretically possible but fragile.

**What works**: Copying a `.jsonl` file gives you a copy of the event history. The old `experimental_resume` config option (`experimental_resume = "/path/to/session.jsonl"`) could load an arbitrary JSONL path. This was removed when native `codex resume` landed (per issue #4393, closed November 2025).

**The obstacle**: The session UUID is embedded *inside* the JSONL content, not just in the filename. If you copy the file without changing the internal UUID, both the original and the copy share an ID. The resume logic uses the internal ID. Whether two sessions with the same internal ID conflict is not documented — the behavior is undefined.

**Practical conclusion**: Do not attempt manual fork-by-copy. Use `codex fork` instead. The native command handles UUID generation and metadata registration correctly.

---

## 6. `InitialHistory` Enum (Internal Architecture)

The internal session initialization mode is represented as an enum with three variants:

- `InitialHistory::New` — fresh session
- `InitialHistory::Resumed` — continuation of an existing thread (same UUID, appends to same rollout file)
- `InitialHistory::Forked` — new UUID, populated from parent's event history (different rollout file, `forked_from_id` set)

This distinction matters for Meridian's harness adapter: `resume` and `fork` are different code paths, not just different initial messages.

---

## 7. Non-Interactive (`codex exec`) Session Support

```
codex exec resume --last "follow-up prompt"
codex exec resume <SESSION_ID> "follow-up prompt"
codex exec resume --last --image screenshot.png "describe this"
```

This enables automation tooling (like Meridian) to programmatically continue or branch sessions without interactive UI.

No equivalent `codex exec fork` is documented, though `codex fork <SESSION_ID>` can be run non-interactively since it only opens the interactive session *after* forking.

---

## 8. Key Limitations for Meridian Integration

| Capability | Status |
|---|---|
| Resume a session by ID | Supported: `codex resume <UUID>` |
| Resume most recent session | Supported: `codex resume --last` |
| Fork a session by ID | Supported: `codex fork <UUID>` |
| Fork most recent session | Supported: `codex fork --last` |
| Inject session ID at launch | Not supported (feature request #13242) |
| Non-interactive resume | Supported: `codex exec resume` |
| Non-interactive fork | Not directly supported |
| Manual fork by file copy | Fragile; internal UUID conflict risk |
| SDK-level fork API | Unverified; treat as not available |

The biggest gap for Meridian is the inability to specify a session UUID at launch. This means an orchestrator must start Codex first and then discover the assigned UUID by parsing output or scanning the sessions directory — unlike Claude Code which supports caller-supplied session IDs.

---

## Sources

- [Command line options – Codex CLI](https://developers.openai.com/codex/cli/reference)
- [Features – Codex CLI](https://developers.openai.com/codex/cli/features)
- [Slash commands in Codex CLI](https://developers.openai.com/codex/cli/slash-commands)
- [Session Resumption – DeepWiki](https://deepwiki.com/openai/codex/4.4-session-resumption)
- [codex fork – Mintlify docs](https://www.mintlify.com/openai/codex/cli/fork)
- [Issue #13242: --session-id flag](https://github.com/openai/codex/issues/13242)
- [Issue #7575: Save session state and branch](https://github.com/openai/codex/issues/7575)
- [Issue #4972: Fork/backtrack API in SDK](https://github.com/openai/codex/issues/4972)
- [Issue #4514: Forking sessions](https://github.com/openai/codex/issues/4514)
- [Issue #4393: experimental_resume restoration](https://github.com/openai/codex/issues/4393)
- [Discussion #3827: Session/Rollout Files](https://github.com/openai/codex/discussions/3827)
- [Discussion #1076: Resuming a previous session](https://github.com/openai/codex/discussions/1076)
- [DEV.to: No resume so I built one](https://dev.to/shinshin86/no-resume-in-codex-cli-so-i-built-one-quickly-continue-with-codex-history-list-50be)
- [X: experimental_resume workaround](https://x.com/tomsiwik/status/1953558364665131159)
