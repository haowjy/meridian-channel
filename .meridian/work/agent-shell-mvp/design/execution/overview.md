# Execution Overview

> What this is: the local runtime model for packaged MCP servers and shell-owned
> coordination code.
>
> What this is not: a shell-owned scientific environment design.

Back up to [../overview.md](../overview.md).

## 1. Correction

The old corpus treated biomedical runtime pieces as shell-owned. That is
removed. The shell owns **coordination**, not domain execution stacks.

## 2. V0 Model

- The user project is a normal `uv`-managed Python project.
- Packages may launch local MCP server subprocesses.
- Those subprocesses own their own domain libraries and any sessionful logic.
- The shell owns lifecycle, relay, and work-item conventions, not domain
  kernels or global scientific virtualenvs.

## 3. Docs

- [local-model.md](./local-model.md) defines local subprocess execution and the
  explicit removal of shell-owned venvs.
- [project-layout.md](./project-layout.md) defines the normal project shape the
  shell expects.
