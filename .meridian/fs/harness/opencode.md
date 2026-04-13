# OpenCode Harness Adapter

Source: `src/meridian/lib/harness/opencode.py`

## Command Shape

Non-interactive spawn:
```
opencode run [--model <model>] [--variant <effort>] [--session <session_id>] [--fork] -  # stdin prompt
```

Interactive (primary launch):
```
opencode [--model <model>] ...
```

Prompt is passed via stdin (stdin support enabled). The model flag strips an `opencode-` prefix if present (so routing alias `opencode-gemini-2.0-flash` becomes `--model gemini-2.0-flash`).

## Capabilities

`supports_stream_events`, `supports_stdin_prompt`, `supports_session_resume`, `supports_session_fork`, `supports_native_skills`, `supports_primary_launch` all enabled. No native agents, no programmatic tools.

## Session Handling

**Resume:** `opencode run --session <session_id>` — session ID appended after the strategy map processes other flags.

**Fork:** `opencode run --session <session_id> --fork` — same as resume but with fork flag.

`seed_session()` for both resume and fork just returns `SessionSeed(session_id=harness_session_id)` — OpenCode accepts the session ID directly, no generation needed.

On resume, `filter_launch_content()` returns `PromptPolicy()` with no prompt — resume sessions don't need a new prompt since the harness reloads conversation history.

## Session Detection (Primary Launch)

`detect_primary_session_id()` scans `~/.local/share/opencode/log/*.log` for entries matching the pattern:
```
<level>  <YYYY-MM-DDTHH:MM:SS>  +Nms  service=session  id=<session_id>  ...  directory=<path>  ...  created
```

Filters to entries timestamped after the spawn started and whose `directory` resolves to the repo root. Returns the session ID from the most recently timestamped match.

`owns_untracked_session()` does the same scan but matches a specific session ID rather than searching for the newest one.

## Permissions

Permissions are passed via the `OPENCODE_PERMISSION` environment variable. `env_overrides()` sets this from `config.opencode_permission_override` if configured.

## Model Prefix Stripping

OpenCode routing in `model_policy.py` maps models with `opencode-` prefixes, `gemini-*`, and `*/*` (slash-separated) patterns to this harness. The `opencode-` prefix is stripped before passing to the CLI since the harness doesn't expect it.

## Skill Handling

Skills are dropped (`FlagEffect.DROP`) in the strategy map — OpenCode doesn't have a native skill loading mechanism equivalent to Claude's `--append-system-prompt`. Skills are composed into the prompt body by the launch layer instead.

Primary launch inventory follows the same rule. The startup `# Meridian Agents` block is composed into the inline primary prompt body for fresh and forked sessions rather than being sent through a separate system channel.

On resume, `filter_launch_content()` still suppresses fresh startup prompt composition, so no new inventory block is injected.

## Effort Mapping

Effort maps to `--variant <value>` (e.g., `--variant thinking` for high reasoning).
