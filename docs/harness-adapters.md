# Harness Adapters

meridian doesn't call LLMs directly. It routes runs to **harness CLIs** (Claude, Codex, OpenCode) or the **Anthropic Messages API** (DirectAdapter). The `HarnessAdapter` Protocol insulates meridian from changes in each CLI's interface.

## Model Routing

meridian automatically picks the right harness based on the model name:

| Model pattern | Harness | Examples |
|--------------|---------|----------|
| `claude-*`, `opus*`, `sonnet*`, `haiku*` | Claude CLI | `claude-opus-4-6`, `sonnet`, `haiku` |
| `gpt-*`, `o1*`, `o3*`, `o4*`, `codex*` | Codex CLI | `gpt-5.3-codex`, `codex`, `o4-mini` |
| `opencode-*`, contains `/` | OpenCode CLI | `opencode-gemini`, `google/gemini-pro` |
| Any (with `--mode direct`) | DirectAdapter | API-only, no CLI |

Unknown models fall back to Codex with a warning.

## Adapters

### Claude CLI

```
claude -p <prompt> --model <model> --output-format stream-json
       [--allowedTools ...] [--permission-prompt-tool ...]
```

**Capabilities:** streaming, session resume, native skills

Supports:
- Permission tier flags (`--allowedTools`, `--dangerously-skip-permissions`)
- Report path injection (tells the agent where to write `report.md`)
- Session resume for `run continue`

### Codex CLI

```
codex exec --model <model> --output-format stream-json <prompt>
      [--sandbox ...] [--agent ...]
```

**Capabilities:** streaming, session resume, native skills

### OpenCode CLI

```
opencode run --model <model> --output-format stream-json <prompt>
```

**Capabilities:** streaming, session resume, native skills

Strips the `opencode-` prefix from model names before passing to the CLI.

### DirectAdapter (Anthropic API)

Calls the Anthropic Messages API directly using `urllib.request`. No CLI harness involved.

**Capabilities:** programmatic tool calling (no streaming, no session resume)

Features:
- Generates tool definitions from the Operation Registry
- Sets `allowed_callers: ["code_execution_20260120"]` for programmatic tool calling
- Supports `code_execution_20260120` tool for sandbox code execution
- Requires `ANTHROPIC_API_KEY` environment variable

Use `direct` mode when you need the agent to call meridian operations as native API tools rather than parsing CLI output.

## Model Catalog

Six built-in models, extensible via `.meridian/models.toml`:

| ID | Alias | Cost | Best for |
|----|-------|------|----------|
| `claude-opus-4-6` | `opus` | $$$ | Architecture, subtle correctness |
| `gpt-5.3-codex` | `codex` | $ | Fast implementation, code generation |
| `claude-sonnet-4-6` | `sonnet` | $$ | UI iteration, fast generalist |
| `claude-haiku-4-5` | `haiku` | $ | Commit messages, quick transforms |
| `gpt-5.2-high` | `gpt52h` | $$ | Escalation solver |
| `gemini-3.1-pro` | `gemini` | $$ | Research, multimodal |

Use aliases for convenience:

```bash
meridian run create -p "..." -m opus      # claude-opus-4-6
meridian run create -p "..." -m codex     # gpt-5.3-codex
meridian run create -p "..." -m haiku     # claude-haiku-4-5
```

### Custom models

Add models to `.meridian/models.toml`:

```toml
[models.my-model]
id = "my-custom-model-v1"
aliases = ["mymodel", "mm"]
harness = "opencode"
cost_tier = "$$"
description = "My custom model"
```

## Adapter Protocol

All adapters implement the `HarnessAdapter` Protocol:

```python
class HarnessAdapter(Protocol):
    @property
    def harness_id(self) -> str: ...

    @property
    def capabilities(self) -> HarnessCapabilities: ...

    def build_command(
        self, params: RunParams, permissions: list[str],
    ) -> list[str]: ...
```

To add a new harness, implement this protocol and register it with `HarnessRegistry`.
