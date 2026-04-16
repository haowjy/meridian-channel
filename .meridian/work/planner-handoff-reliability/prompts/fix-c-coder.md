# Task — fix stale help text at `src/meridian/cli/main.py:771`

The `spawn_app` help string currently reads:

```
Run subagents with a model and prompt.
Runs in background by default. Use --foreground to block.
```

Both sentences after the first are wrong:

1. **"Runs in background by default"** — actually the default is foreground. Verified against `src/meridian/cli/spawn.py:218` where `background: ... = False`.
2. **"Use --foreground to block"** — there is no `--foreground` flag. The only relevant flag is `--background`, which is opt-in.

## Fix

Replace the help text at `src/meridian/cli/main.py` (around line 770) so it reads:

```
Run subagents with a model and prompt.
Runs in foreground by default; returns when the spawn reaches a terminal state. Use --background to return immediately with the spawn ID.
```

Keep the existing structure (the `help=(... )` concatenation pattern and the `help_epilogue` block right below). Only the two-line help string changes.

## Verification

- `uv run pyright` — 0 errors.
- `uv run ruff check .` — clean.
- `uv run meridian spawn --help` — quickly eyeball the rendered help. The summary should now accurately describe the default.

## Don't

- Don't touch `spawn.py` or any other file.
- Don't change the `help_epilogue` examples — they're fine.
- Don't commit.

## Report

1. Exact before/after text.
2. pyright + ruff output.
3. A short quote from `meridian spawn --help` showing the new summary line.
