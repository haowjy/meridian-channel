# Harness Subcommand Refactor

## Problem

`meridian claude`, `meridian codex`, `meridian opencode` are registered as individual commands via `_register_harness_shortcut_command()` (main.py:753–874). Each duplicates ~80 lines of parameter declarations identical to the root command, and only supports primary launch — `meridian codex spawn ...` doesn't work.

The shortcut commands already call the shared `_run_primary_launch()` with `harness=harness_name`, so they're conceptually thin wrappers. But the implementation is heavy (duplicated params) and incomplete (no spawn support).

## Current Flow

```
meridian codex -m sonnet       → _register_harness_shortcut_command("codex")
                                 → shortcut() with all params duplicated
                                 → _run_primary_launch(harness="codex", model="sonnet", ...)

meridian --harness codex -m sonnet → root() → _run_primary_launch(harness="codex", ...)

meridian codex spawn -m sonnet  → ERROR: "spawn" consumed as passthrough arg
```

Both the shortcut and `--harness` already converge in `_run_primary_launch`, which passes harness into `LaunchRequest.harness`, which becomes `RuntimeOverrides.harness` at CLI precedence (highest). The resolution pipeline in `resolve_policies()` already handles this correctly.

For spawn, `SpawnCreateInput.harness` exists but isn't exposed as a CLI flag.

## Design

### Approach: argv rewriting in `main()`

Rather than making each harness name a cyclopts sub-App (which would require re-registering all subcommands under each harness group and fighting cyclopts' argument parsing), rewrite argv before cyclopts sees it.

When `main()` detects the first positional token is a harness name (`claude`, `codex`, `opencode`):

1. Strip the harness name from argv
2. Inject `--harness <name>` at the front of the remaining args
3. Let normal dispatch handle the rest

This means:
- `meridian codex -m sonnet` → `meridian --harness codex -m sonnet` → root command, primary launch
- `meridian codex spawn -m sonnet -p test` → `meridian --harness codex spawn -m sonnet -p test` → spawn command
- `meridian codex` → `meridian --harness codex` → root command, default model from resolution

### Changes Required

**`src/meridian/cli/main.py`**

1. **Delete `_register_harness_shortcut_command()`** and the registration loop (lines 753–874). This removes ~120 lines of duplicated parameter declarations.

2. **Add harness name detection in `main()`**, after `_extract_global_options()` but before `app(cleaned_args)`. Pseudocode:

   ```python
   _HARNESS_SHORTCUTS = frozenset({"claude", "codex", "opencode"})

   # In main(), after cleaned_args is computed:
   if cleaned_args and cleaned_args[0] in _HARNESS_SHORTCUTS:
       harness_name = cleaned_args[0]
       cleaned_args = ["--harness", harness_name] + cleaned_args[1:]
   ```

3. **Update `_validate_top_level_command()`** — harness names are no longer registered commands, so the validator needs to recognize them. The simplest fix: the rewriting happens before validation, so `_validate_top_level_command` sees `--harness codex spawn` which already parses correctly (first positional is `spawn`, a known command) or `--harness codex` (no positional, falls through to root default).

4. **Update `_top_level_command_names()`** — no change needed since harness commands won't be registered anymore, but the help text in `app` should still mention the shortcuts.

5. **Update help text** — the app help string already says "Harness shortcuts: meridian claude, meridian codex, meridian opencode". Keep this, but since the shortcuts won't appear in cyclopts' auto-generated command list, consider adding a note or keeping them as no-op commands that print help.

**`src/meridian/cli/spawn.py`**

6. **Add `--harness` flag to `_spawn_create()`** — expose the existing `SpawnCreateInput.harness` field as a CLI parameter. When `meridian codex spawn ...` is invoked, `--harness codex` is in argv before `spawn`, so it's consumed by `_extract_global_options()` if treated as a global flag, or by the root command. 

   **Wait** — `--harness` is currently a root-command parameter, not a global option extracted in `_extract_global_options()`. For the rewrite approach to work with spawn, `--harness` needs to either:
   - (a) Become a global option extracted before dispatch (like `--json`, `--config`), or
   - (b) Be passed through to spawn via a different mechanism

   **Option (a) is simpler**: add `--harness` to `_extract_global_options()` and store it in `GlobalOptions`. Then both root and spawn read it from the same place.

### Revised Change List

**`src/meridian/cli/main.py`**

1. **Add `harness` to `GlobalOptions`** — new optional field.

2. **Extract `--harness` in `_extract_global_options()`** — alongside `--json`, `--config`, etc. Add it to `_TOP_LEVEL_VALUE_FLAGS` (already there for `_first_positional_token`).

3. **Rewrite harness shortcuts in `main()`**:
   ```python
   _HARNESS_SHORTCUTS = frozenset({"claude", "codex", "opencode"})

   # After _extract_global_options:
   if cleaned_args and cleaned_args[0] in _HARNESS_SHORTCUTS:
       harness_name = cleaned_args.pop(0)
       options = options.model_copy(update={"harness": harness_name})
   ```

4. **Pass `options.harness` to root command** — the root command's `harness` parameter gets its value from `GlobalOptions.harness` when not explicitly set.

5. **Delete `_register_harness_shortcut_command()`** and the loop.

6. **Keep harness names in `_top_level_command_names()` return set** so `_validate_top_level_command()` doesn't reject them. Or do the rewrite before validation.

**`src/meridian/cli/spawn.py`**

7. **Read harness from `GlobalOptions`** in `_spawn_create()` and pass to `SpawnCreateInput(harness=...)`.

### Ordering in `main()`

```
argv
  → _extract_global_options()     # extracts --harness, --json, --config, etc.
  → harness shortcut rewrite      # "codex spawn ..." → options.harness="codex", args=["spawn", ...]
  → _validate_top_level_command() # sees "spawn" as first positional — valid
  → app(cleaned_args)             # normal cyclopts dispatch
```

### Edge Cases

| Scenario | Behavior |
|---|---|
| `meridian codex --harness claude` | Conflict: shortcut sets codex, flag sets claude. Error: "Cannot specify --harness with a harness shortcut." |
| `meridian codex spawn --from p123` | Rewrites to `meridian --harness codex spawn --from p123`. Spawn reads harness from GlobalOptions. |
| `meridian codex --continue s123` | Rewrites to `meridian --harness codex --continue s123`. Primary launch with forced harness + session resume. Existing validation in `_run_primary_launch` handles harness/session conflicts. |
| `meridian codex --model opus` | Primary launch, harness=codex, model=opus. `resolve_policies` validates compatibility — opus routes to claude, not codex, so it errors. This is correct behavior. |
| `meridian --harness codex spawn -m gpt-5.3-codex -p "test"` | Works today via flag. After refactor, also works via shortcut. |
| `meridian codex --help` | Should show root help (or codex-specific help text). Since codex is rewritten to `--harness codex`, help shows root help. Acceptable — the shortcut is just sugar. |

### Compatibility Note

`--harness` already exists as a root-command flag and is already in `_TOP_LEVEL_VALUE_FLAGS`. Extracting it as a global option is a behavior change: it'll be consumed before cyclopts sees it instead of being parsed by the root command handler. This is fine because the value still reaches the same place — `_run_primary_launch`'s `harness` parameter — just via `GlobalOptions` instead of cyclopts parameter binding.

## Files to Change

| File | Change |
|---|---|
| `src/meridian/cli/main.py` | Add harness to GlobalOptions, extract in global options, rewrite shortcuts, delete `_register_harness_shortcut_command`, pass harness to root/spawn |
| `src/meridian/cli/spawn.py` | Read harness from GlobalOptions, pass to SpawnCreateInput |

## What This Doesn't Change

- `resolve_policies()` — untouched, already handles harness at CLI precedence
- `LaunchRequest` / `RuntimeOverrides` — untouched, already have harness fields
- `SpawnCreateInput` — untouched, already has harness field
- Harness adapters — untouched
- Model-harness compatibility validation — untouched, already in resolve pipeline
