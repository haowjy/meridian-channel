# Agent Mode

Agent mode should narrow the visible CLI surface and use per-command output defaults. These checks are small but important because subagents rely on this contract.

## Setup

```bash
export REPO_ROOT=/abs/path/to/meridian-channel
export SMOKE_REPO="$(mktemp -d /tmp/meridian-agent-mode.XXXXXX)"
git -C "$SMOKE_REPO" init --quiet
for var in $(env | awk -F= '/^MERIDIAN_/ {print $1}'); do unset "$var"; done
export MERIDIAN_PROJECT_DIR="$SMOKE_REPO"
export MERIDIAN_RUNTIME_DIR="$SMOKE_REPO/.meridian"
cd "$REPO_ROOT"
test -d "$SMOKE_REPO/.git" && echo "PASS: agent-mode repo ready" || echo "FAIL: agent-mode repo setup failed"
```

### AGT-1. Agent help is restricted [IMPORTANT]

```bash
MERIDIAN_DEPTH=1 uv run meridian --help > /tmp/meridian-agent-help.txt && \
uv run python - <<'PY'
text = open("/tmp/meridian-agent-help.txt").read()
for visible in ("spawn", "work", "models"):
    assert visible in text
for hidden in ("config", "doctor", "init", "session", "completion", "serve", "claude", "codex", "opencode"):
    assert hidden not in text
print("PASS: agent-mode help is restricted")
PY
```

### AGT-2. `--human` restores the full help surface [IMPORTANT]

```bash
MERIDIAN_DEPTH=1 uv run meridian --human --help > /tmp/meridian-agent-human-help.txt && \
uv run python - <<'PY'
text = open("/tmp/meridian-agent-human-help.txt").read()
for visible in ("config", "doctor", "init", "session", "spawn", "work", "claude", "codex", "opencode", "serve"):
    assert visible in text
print("PASS: --human restored full help")
PY
```

### AGT-3. Agent mode uses per-command defaults [IMPORTANT]

Agent mode now uses per-command defaults. Read/browse commands like `models list`
default to text; control-plane commands default to JSON.

```bash
# models list defaults to text in agent mode
MERIDIAN_DEPTH=1 uv run meridian models list > /tmp/meridian-agent-models.out && \
uv run python - <<'PY'
text = open("/tmp/meridian-agent-models.out").read()
assert not text.strip().startswith("{"), "Expected text, got JSON"
print("PASS: models list output is text in agent mode")
PY
```

### AGT-4. Explicit --format json overrides agent defaults [IMPORTANT]

```bash
MERIDIAN_DEPTH=1 uv run meridian --format json models list > /tmp/meridian-explicit-json.out && \
uv run python - <<'PY'
import json
for line in open("/tmp/meridian-explicit-json.out"):
    line = line.strip()
    if line:
        json.loads(line)
print("PASS: --format json produces JSON")
PY
```
