# Claude Harness Adapter

Source: `src/meridian/lib/harness/claude.py`

## Command Shape

Non-interactive (default spawn mode):
```
claude -p --output-format stream-json --verbose --model <model> [--agent <agent>] \
  [--append-system-prompt <skills>] [--agents <json>] [--resume <session_id>] [--fork-session] \
  [permission flags...] -p -  # prompt via stdin
```

Interactive (primary launch, `run.interactive=True`):
```
claude [--model <model>] [--agent <agent>] ...  # no -p, no stream-json
```

`--verbose` is required when using `stream-json` output with `-p`. The prompt is always passed via stdin (`-`), not inline in the command.

## Capabilities

All capabilities enabled except `supports_programmatic_tools`. Is the only harness with `supports_native_agents=True`.

## Session Handling

**Fresh sessions:** `seed_session()` generates a UUID4 and injects `--session-id <uuid>`. This lets Meridian know the session ID before the process starts, unlike Codex which requires post-launch discovery.

**Resume:** `--resume <harness_session_id>` appended to command.

**Fork:** `--resume <harness_session_id> --fork-session` — fork from an existing session into a new one.

**Passthrough:** If user passed `--session-id` via `extra_args`, that value is used instead of a generated UUID.

## Skill Injection

Claude doesn't expand profile skills via `--agent` (issue #29902 workaround). Skills are injected as `--append-system-prompt <content>` instead. `run_prompt_policy()` returns `skill_injection_mode="append-system-prompt"` with `include_agent_body=False, include_skills=False` — the launch layer handles composition, not Claude's native profile loading.

Primary launch inventory injection uses this same channel. Fresh and forked primary sessions append the startup `# Meridian Agents` block to the `--append-system-prompt` payload, so Claude sees the installed agent catalog in its startup system context without flattening that catalog into the interactive user prompt body.

## Agent Loading

For agent profiles, `build_adhoc_agent_payload()` builds a JSON blob: `{"<name>": {"description": "...", "prompt": "..."}}` passed as `--agents <json>`. This is the Claude-specific mechanism for installing a Meridian agent profile as a native Claude agent.

## Environment

`blocked_child_env_vars()` returns `{"CLAUDECODE"}`. Rationale: Claude Code sets `CLAUDECODE` in its env to detect nesting. Meridian manages its own nesting depth, so it suppresses this var in child spawns to let nested Claude processes run normally under Meridian control.

## Session Detection (Primary Launch)

`detect_primary_session_id()` scans `~/.claude/projects/<repo-slug>/` for JSONL session files modified after the spawn started. Returns the session ID from the most recent matching file. Project dir slugification: `re.sub(r"[^a-zA-Z0-9]", "-", str(repo_root.resolve()))`.

Also checks slug-prefixed sibling directories (e.g., if Claude created a slightly different slug variant).

## Artifact Extraction

- Usage: parsed from `output.jsonl` (Claude stream-json output format)
- Session ID: extracted from output artifacts via Claude-specific JSON key patterns
- Report: extracted from last assistant message in `output.jsonl` if `report.md` not present
- Conversation: full turn/tool-call reconstruction from `output.jsonl` + `prompt.md` + `report.md`

## Effort Mapping

Internal effort strings map to Claude's `--effort` values:
- `low` → `low`, `medium` → `medium`, `high` → `high`, `xhigh` → `max`
