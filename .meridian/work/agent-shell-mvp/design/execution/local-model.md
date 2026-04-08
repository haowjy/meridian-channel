# Local Model

> What this is: the local execution model for packaged MCP servers and shell
> coordination code.
>
> What this is not: a shell-owned domain runtime.

Back up to [overview.md](./overview.md).

## 1. Correction

The shell no longer owns:

- a biomedical virtualenv,
- a persistent scientific kernel,
- PyVista subprocesses launched as shell internals, or
- preinstalled domain stacks under `~/.meridian/venvs/...`.

Those assumptions are removed everywhere in this pass.

## 2. V0 Local Execution

The shell launches two kinds of local processes:

- the harness process, and
- package-declared MCP server subprocesses.

The shell owns lifecycle, stdout/stderr capture, relay, and work-item
conventions. The packaged MCP server owns its own domain libraries and any
sessionful application state it needs.

## 3. Package-Declared Launch

Typical local MCP launch looks like:

```text
uv run python -m some_package.server
```

or another package-declared command surfaced through the generated mars
registry. The shell does not guess package environments. It executes what the
package declares in the context of the user's project.

## 4. Codex Correction

**H2 disposition:** the old "Codex app-server breaks persistent-kernel tool
execution" finding is obsolete because the shell no longer embeds that kernel.
Codex only needs to cooperate with the same shell-owned coordination surfaces
and packaged MCP subprocesses as every other adapter.

## 5. Files-As-Authority

The shell still owns work-item conventions:

- package outputs written under the active work item,
- relay-visible artifacts stored on disk before publication when needed, and
- shell-side logs and state under `.meridian/`.

What changed is **who owns the domain process**, not whether outputs land on
disk.

## 6. Non-Goals

- no shell-managed domain dependency installer,
- no shell-owned global analysis environment,
- no biomedical-specific bootstrap command in the shell core.
