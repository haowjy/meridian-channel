# Streaming Adapter Parity

Manual smoke matrix for subprocess projection (`spawn --dry-run`) versus streaming transport projection (connection-layer launch spec handling).

## Setup

```bash
export REPO_ROOT=/abs/path/to/meridian-channel
cd "$REPO_ROOT"
uv run meridian --help >/dev/null && echo "PASS: meridian CLI is runnable" || echo "FAIL: meridian CLI is not runnable"
```

### SAP-1. Claude: effort, agent, skills parity [CRITICAL]

```bash
uv run meridian --json spawn \
  -m claude-sonnet-4-6 \
  -a coder \
  -s verification \
  --effort xhigh \
  --dry-run \
  -p "Claude parity smoke" >/tmp/meridian-parity-claude-dry.json && \
uv run python - <<'PY'
import json
doc = json.load(open("/tmp/meridian-parity-claude-dry.json"))
cmd = doc["cli_command"]
assert "--model" in cmd and "claude-sonnet-4-6" in cmd
assert "--effort" in cmd and "max" in cmd
assert "--agent" in cmd and "coder" in cmd
assert any(flag in cmd for flag in ("--append-system-prompt", "--agents"))
print("PASS: Claude subprocess projection includes model/effort/agent/skills")
PY
```

```bash
uv run pytest-llm tests/harness/test_launch_spec_parity.py -k claude_cross_transport_parity_on_semantic_fields -q && \
echo "PASS: Claude subprocess vs streaming semantic parity"
```

### SAP-2. Codex: effort + approval mode parity [CRITICAL]

```bash
uv run meridian --json spawn \
  -m gpt-5.3-codex \
  --effort high \
  --approval confirm \
  --dry-run \
  -p "Codex parity smoke" >/tmp/meridian-parity-codex-dry.json && \
uv run python - <<'PY'
import json
doc = json.load(open("/tmp/meridian-parity-codex-dry.json"))
cmd = doc["cli_command"]
assert "--model" in cmd and "gpt-5.3-codex" in cmd
assert "-c" in cmd and any("model_reasoning_effort=\"high\"" in part for part in cmd)
print("PASS: Codex subprocess projection includes model + effort")
PY
```

```bash
uv run pytest-llm tests/harness/test_launch_spec_parity.py -k codex_cross_transport_parity_on_semantic_fields -q && \
uv run pytest-llm tests/harness/test_codex_ws.py -k "auto_accepts_command_execution_approval_requests or rejects_approval_requests_in_confirm_mode" -q && \
echo "PASS: Codex streaming parity and approval-mode behavior"
```

### SAP-3. OpenCode: model normalization parity [CRITICAL]

```bash
uv run meridian --json spawn \
  -m opencode-gpt-5.3-codex \
  --effort medium \
  --dry-run \
  -p "OpenCode parity smoke" >/tmp/meridian-parity-opencode-dry.json && \
uv run python - <<'PY'
import json
doc = json.load(open("/tmp/meridian-parity-opencode-dry.json"))
cmd = doc["cli_command"]
assert "--model" in cmd and "gpt-5.3-codex" in cmd
assert "--variant" in cmd and "medium" in cmd
print("PASS: OpenCode subprocess projection includes normalized model + effort variant")
PY
```

```bash
uv run pytest-llm tests/harness/test_launch_spec_parity.py -k opencode_cross_transport_parity_with_known_streaming_asymmetries -q && \
echo "PASS: OpenCode streaming parity for normalized model/session fields"
```

Known asymmetry to confirm each run: OpenCode streaming currently ignores effort and fork transport fields; parity only applies to shared semantic fields (normalized model and session continuation).
