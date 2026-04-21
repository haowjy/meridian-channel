# Plugin API

`meridian.plugin_api` is the stable public contract for hook and plugin authors. It version-pins at `1.0.0` and exposes only the symbols intended for external use.

Install meridian-cli and import from this package directly — do not import from internal submodules.

```python
from meridian.plugin_api import Hook, HookContext, HookResult, HookOutcome
```

## Version

```python
import meridian.plugin_api as api
print(api.__version__)  # "1.0.0"
```

## Hook Types

| Export | Purpose |
| ------ | ------- |
| `Hook` | Resolved hook record — fields like `name`, `event`, `builtin`, `command`, `options`, `remote` |
| `HookContext` | Runtime context passed to a hook at execution time — spawn state, work item, event name |
| `HookResult` | Return value from a hook execution |
| `HookOutcome` | Enum: outcome of a hook run (`success`, `failure`, `skipped`) |
| `HookEventName` | String literal type for valid event names (`spawn.start`, `spawn.finalized`, `work.start`, `work.done`) |
| `FailurePolicy` | String literal type for failure policy values (`fail`, `warn`, `ignore`) |

## State Helpers

```python
from meridian.plugin_api import get_project_state_root, get_user_state_root

# Resolve the per-machine state root for the current project
state_root = get_project_state_root()

# Resolve the user-level Meridian state root (~/.meridian or %LOCALAPPDATA%\meridian)
user_root = get_user_state_root()
```

## Git Helpers

Used by `git-autosync` and useful for any hook that operates on a remote repo.

```python
from meridian.plugin_api import generate_repo_slug, normalize_repo_url, resolve_clone_path

url = "git@github.com:team/docs.git"
slug = generate_repo_slug(url)           # "github.com-team-docs"
normalized = normalize_repo_url(url)     # canonical form
clone_path = resolve_clone_path(url)     # path where the repo would be cloned
```

## Config Helpers

```python
from meridian.plugin_api import get_user_config, get_git_overrides

config = get_user_config()          # parsed user config dict
overrides = get_git_overrides()     # config values from git config
```

## File Locking

```python
from meridian.plugin_api import file_lock

with file_lock("/path/to/lockfile"):
    # exclusive section
    ...
```

Cross-process file lock. Use this in hooks that must not run concurrently across spawns.

## Writing a Hook

A minimal custom hook registered via `command`:

```toml
# meridian.toml
[[hooks]]
name    = "notify"
command = "notify-send 'spawn done'"
event   = "spawn.finalized"
```

A Python builtin-style hook using the plugin API (for hooks distributed as packages):

```python
from meridian.plugin_api import HookContext, HookResult, HookOutcome

def run(ctx: HookContext) -> HookResult:
    print(f"Hook fired for event: {ctx.event}")
    return HookResult(outcome=HookOutcome.SUCCESS)
```

See [hooks.md](hooks.md) for hook configuration schema and available builtins.
