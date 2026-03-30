# Claude Code Session Management: Research Report

Date: 2026-03-29

## Summary

Claude Code has a well-defined, file-based session system stored as JSONL files under `~/.claude/projects/`. It supports session resumption, forking, and naming. There is no native "fork by copying files" approach needed — the `--fork-session` flag handles this natively. The session format is inspectable and documented enough to understand what a fork does at the file level.

---

## 1. How `claude --continue` Works

`claude --continue` (alias `-c`) resumes the most recent conversation in the **current working directory**. The resolution process:

1. Read the current working directory.
2. Encode the path: replace every `/` (and non-alphanumeric characters more broadly) with `-`. So `/home/alice/code/project` becomes `-home-alice-code-project`.
3. Look up `~/.claude/projects/<encoded-path>/` for session files.
4. Load the most recently modified `.jsonl` session file in that directory.
5. Resume by appending new messages to that same file under the same session ID.

When you `--continue`, new messages are appended to the existing JSONL file. The session ID (UUID) in the file stays the same. The conversation context is reconstructed by reading the full JSONL and replaying the `parentUuid` chain.

## 2. Where Claude Code Stores Conversation History

### Directory structure

```
~/.claude/
  history.jsonl              # global lightweight index: every prompt ever sent
  projects/
    -home-user-myproject/    # path-encoded project name
      <session-uuid>.jsonl   # full conversation transcript (one per session)
      <session-uuid>.jsonl   # another session in same project
      sessions-index.json    # metadata: summaries, message counts, git branches, timestamps
      memory/
        MEMORY.md            # auto-memory notes Claude saves to itself
```

### JSONL record format

Each line in a session `.jsonl` file is one JSON event. Key fields:

| Field | Description |
|---|---|
| `type` | `user`, `assistant`, `system`, `progress` |
| `sessionId` | UUID identifying the session that owns this record |
| `uuid` | UUID for this individual record |
| `parentUuid` | UUID of the previous record (creates a linked chain) |
| `timestamp` | ISO 8601 UTC |
| `cwd` | Working directory when message was sent |
| `version` | Claude Code version |
| `gitBranch` | Current git branch |
| `slug` | Human-readable conversation-level name (persists across continuations) |
| `isSidechain` | Used for subagent-spawned sidechains |
| `message` | Object with `role` and `content` array |

Content blocks in `message.content` are typed: `text`, `tool_use`, `tool_result`, `thinking`.

### Compaction boundaries

When context fills up (~167K tokens), Claude writes a `compact_boundary` system record with:
- `subtype: "compact_boundary"`
- `logicalParentUuid`: references the last real message before compaction
- `parentUuid: null`: resets the chain
- `compactMetadata`: includes `trigger` ("auto" or "manual") and `preTokens`

Immediately after, a synthetic user message with `isCompactSummary: true` carries the compaction summary. This should be skipped when reconstructing real conversation flow.

## 3. The `--fork-session` Flag

There is a native `--fork-session` flag. No manual file copying is needed.

```bash
# Fork the most recent session in cwd
claude --continue --fork-session

# Fork a specific session by ID or name
claude --resume <session-id> --fork-session
claude --resume <session-name> --fork-session
```

**What it does:** Creates a new session UUID while preserving the full conversation history from the source session. The original session remains untouched. The fork and original diverge independently from the fork point.

There is also a `/fork` slash command available inside an active session (added as an in-session UI convenience after the CLI flag existed).

## 4. File-Level Mechanics of Forking

When `--fork-session` creates a fork, the resulting JSONL file has a distinctive structure that reveals the relationship:

1. **New filename**: `<new-session-uuid>.jsonl` (fresh UUID for the fork)
2. **Copied prefix**: The file's initial records carry the **parent session's ID** in their `sessionId` field — they are a verbatim copy of the parent's history up to the fork point.
3. **Transition marker**: A `compact_boundary` record appears at the fork point (identical to or matching one in the parent file).
4. **New session ID takes over**: From the fork point onward, records carry the new session UUID in `sessionId`.
5. **Shared `slug`**: Both the original and forked sessions share the same `slug` field (human-readable name), which serves as the conversation-level lineage identifier.
6. **parentUuid chain stays intact**: The new session's first record after the boundary has `parentUuid` pointing to the parent session's last record UUID, maintaining an unbroken chain.

### The linking signal (no explicit `parentSessionId` field)

There is no dedicated `parentSessionId` or `forkFrom` field. The parent-child relationship is inferred from:
- Records at the start of the file having a `sessionId` different from the filename UUID = those are copied from the parent
- Both files sharing the same `slug`
- The `parentUuid` chain crossing the session ID boundary

## 5. Session ID Format

Session IDs are standard UUID v4 format: `e7d318b1-4274-4ee2-a341-e94893b5df49`.

The session file is named `<session-uuid>.jsonl`.

Sessions can also have human-readable **names** set with `--name <name>` or `/rename` mid-session. Named sessions can be resumed by name: `claude --resume auth-refactor`. The name is stored in the `slug` field and in `sessions-index.json`.

**`--session-id` flag**: You can specify an exact UUID when launching: `claude --session-id "550e8400-e29b-41d4-a716-446655440000"`. This is how you could programmatically control which session file gets written.

## 6. Could We Fork by Copying Files?

Theoretically yes, but `--fork-session` makes it unnecessary. If you wanted to do it manually:

1. Copy `~/.claude/projects/<encoded-path>/<source-session-uuid>.jsonl` to a new file named `<new-uuid>.jsonl`.
2. The copied file's initial records will have `sessionId` = old UUID (the copy prefix pattern Claude itself uses).
3. Launch with `claude --session-id <new-uuid>` to continue into that specific file.

However, this bypasses the `sessions-index.json` metadata, so the session won't appear in the `--resume` picker with correct metadata (summary, timestamps, name) until Claude writes to it and updates the index.

The cleaner path is always `--fork-session` via the CLI.

## 7. Session Persistence Controls

| Flag | Effect |
|---|---|
| `--no-session-persistence` | Disable disk persistence entirely (print mode only) |
| `--session-id <uuid>` | Force a specific session UUID |
| `--name <name>`, `-n` | Set human-readable session name |
| `--from-pr <number>` | Resume sessions linked to a GitHub PR |

## 8. Known Rough Edges

**Same session in multiple terminals**: If two terminals resume the same session ID, both write to the same `.jsonl` file. Messages interleave. Nothing corrupts, but the conversation history becomes jumbled. Use `--fork-session` for parallel work from the same starting point.

**Session-scoped permissions not inherited**: When you fork or resume, any permissions you granted interactively (one-time "yes, allow this tool") are not carried over. You re-approve at the start of the new fork.

**Subagent resume bug (historical, fixed in later versions)**: A bug in `cli.js` caused resumed subagent sessions to always reload from the original checkpoint rather than accumulating new messages (`recordMessagesToSessionStorage: !G` being falsy when `G` is set). Each resume forked from the original rather than the previous resume. This was a code bug, not a design issue.

**After `mv` a project directory**: The encoded path changes. You must manually rename `~/.claude/projects/<old-encoded-path>` to `~/.claude/projects/<new-encoded-path>` to keep session history accessible with `--continue`.

## 9. API / Programmatic Usage

The Agent SDK (platform.claude.com) has a separate session API for multi-turn programmatic conversations, but that is distinct from the CLI's local file-based sessions. The CLI session files are not directly exposed through the API; they are a local CLI concern.

For programmatic forking from code (not CLI), the pattern is:
1. Use `--session-id` to assign a known UUID to the session you want to fork from
2. Copy the JSONL file to a new UUID filename
3. Launch a new `claude` process with `--session-id <new-uuid>` pointing at the copy

Or more simply: shell out to `claude --resume <id> --fork-session` and capture the new session ID from the output or a hook.

---

## Sources

- [Claude Code CLI Reference (official)](https://code.claude.com/docs/en/cli-reference)
- [How Claude Code Works (official)](https://code.claude.com/docs/en/how-claude-code-works)
- [How Claude Code Session Continuation Works (fsck.com, Feb 2026)](https://blog.fsck.com/releases/2026/02/22/claude-code-session-continuation/)
- [Claude Code Session Management - Steve Kinney](https://stevekinney.com/courses/ai-development/claude-code-session-management)
- [Resume, Search, Manage Conversations - kentgigger.com](https://kentgigger.com/posts/claude-code-conversation-history)
- [Feature Request: Session Branching / Conversation Forking - GitHub Issue #12629](https://github.com/anthropics/claude-code/issues/12629)
- [Feature: Conversation branching / fork from message - GitHub Issue #16276](https://github.com/anthropics/claude-code/issues/16276)
- [Bug: Resumable agents fork from checkpoint - GitHub Issue #10856](https://github.com/anthropics/claude-code/issues/10856)
- [Claude Code Session Fork for Ghostty - GitHub Gist (yottahmd)](https://gist.github.com/yottahmd/8e6d0a4213be6a559dfe3dcdd350ce09)
- [Claude Code --continue after Directory mv - GitHub Gist (gwpl)](https://gist.github.com/gwpl/e0b78a711b4a6b2fc4b594c9b9fa2c4c)
- [Anatomy of the .claude/ Folder - Daily Dose of DS](https://blog.dailydoseofds.com/p/anatomy-of-the-claude-folder)
