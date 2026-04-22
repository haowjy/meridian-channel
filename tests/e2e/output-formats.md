# Output Formats

These checks keep the CLI output contract honest across the supported presentation modes. Use them after changing formatting, sinks, or error rendering.

## Setup

```bash
export REPO_ROOT=/abs/path/to/meridian-channel
export SMOKE_REPO="$(mktemp -d /tmp/meridian-formats.XXXXXX)"
git -C "$SMOKE_REPO" init --quiet
for var in $(env | awk -F= '/^MERIDIAN_/ {print $1}'); do unset "$var"; done
export MERIDIAN_PROJECT_DIR="$SMOKE_REPO"
export MERIDIAN_RUNTIME_DIR="$SMOKE_REPO/.meridian"
mkdir -p "$SMOKE_REPO/.agents/agents"
cat > "$SMOKE_REPO/.agents/agents/reviewer.md" <<'EOF'
# Reviewer

Format smoke reviewer.
EOF
cd "$REPO_ROOT"
test -d "$SMOKE_REPO/.git" && echo "PASS: output-format repo ready" || echo "FAIL: output-format repo setup failed"
```

### FMT-1. `--json` returns JSON [CRITICAL]

```bash
uv run meridian --json spawn -a reviewer -p "format probe" --dry-run > /tmp/meridian-formats-json.json && \
uv run python - <<'PY'
import json
assert isinstance(json.load(open("/tmp/meridian-formats-json.json")), dict)
print("PASS: --json produced JSON")
PY
```

### FMT-2. `--format json` matches the JSON contract [CRITICAL]

```bash
uv run meridian --format json spawn -a reviewer -p "format probe" --dry-run > /tmp/meridian-formats-format-json.json && \
uv run python - <<'PY'
import json
assert isinstance(json.load(open("/tmp/meridian-formats-format-json.json")), dict)
print("PASS: --format json produced JSON")
PY
```

### FMT-3. `--format text` is human-readable [IMPORTANT]

```bash
uv run meridian --format text doctor > /tmp/meridian-formats-text.out && \
uv run python - <<'PY'
text = open("/tmp/meridian-formats-text.out").read()
assert "ok:" in text and not text.lstrip().startswith("{")
print("PASS: --format text produced text output")
PY
```

### FMT-4. Agent mode uses per-command defaults [IMPORTANT]

Agent mode now uses per-command defaults instead of forcing JSON globally.
Read/browse commands default to text; control-plane commands default to JSON.

```bash
# models list defaults to text in agent mode
MERIDIAN_DEPTH=1 uv run meridian models list > /tmp/meridian-formats-agent.out && \
uv run python - <<'PY'
text = open("/tmp/meridian-formats-agent.out").read()
assert not text.strip().startswith("{"), "Expected text output"
print("PASS: agent mode used text for models list")
PY
```

### FMT-5. Agent mode JSON default for control-plane commands [IMPORTANT]

```bash
# work current defaults to JSON in agent mode (control-plane command)
export MERIDIAN_PROJECT_DIR="$SMOKE_REPO"
MERIDIAN_DEPTH=1 uv run meridian work current > /tmp/meridian-work-current.out && \
uv run python - <<'PY'
import json
data = json.load(open("/tmp/meridian-work-current.out"))
print("PASS: work current output is JSON in agent mode")
PY
```
