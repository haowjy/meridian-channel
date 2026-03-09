# Quick Sanity

Run these first. They cover the critical command surface in about five minutes and stop you from wasting time on deeper smoke tests when the CLI is already broken.

## Setup

```bash
export REPO_ROOT=/abs/path/to/meridian-channel
export SMOKE_REPO="$(mktemp -d /tmp/meridian-quick.XXXXXX)"
git -C "$SMOKE_REPO" init --quiet
for var in $(env | awk -F= '/^MERIDIAN_/ {print $1}'); do unset "$var"; done
export MERIDIAN_REPO_ROOT="$SMOKE_REPO"
export MERIDIAN_STATE_ROOT="$SMOKE_REPO/.meridian"
cd "$REPO_ROOT"
test -d "$SMOKE_REPO/.git" && echo "PASS: quick-sanity repo ready" || echo "FAIL: quick-sanity repo setup failed"
```

### QS-1. Help text [CRITICAL]

```bash
HELP_TEXT="$(uv run meridian --help 2>&1)" && \
printf '%s\n' "$HELP_TEXT" | grep -q 'spawn' && \
printf '%s\n' "$HELP_TEXT" | grep -q 'report' && \
printf '%s\n' "$HELP_TEXT" | grep -q 'models' && \
printf '%s\n' "$HELP_TEXT" | grep -q 'skills' && \
echo "PASS: help exposes core commands" || echo "FAIL: help is missing core commands"
```

### QS-2. Version [CRITICAL]

```bash
uv run meridian --version 2>&1 | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+' && echo "PASS: version looks valid" || echo "FAIL: version output is malformed"
```

### QS-3. Config init and show [CRITICAL]

```bash
uv run meridian config init >/tmp/meridian-qs-config-init.txt && \
uv run meridian config show >/tmp/meridian-qs-config-show.txt && \
grep -q 'config.toml' /tmp/meridian-qs-config-init.txt && \
grep -q '^defaults.model:' /tmp/meridian-qs-config-show.txt && \
echo "PASS: config init and show work" || echo "FAIL: config init or show output was unexpected"
```

### QS-4. Models list [CRITICAL]

```bash
uv run meridian --json models list >/tmp/meridian-qs-models.txt 2>&1 && \
grep -Eq 'MODEL|gpt-|claude-|gemini-' /tmp/meridian-qs-models.txt && \
echo "PASS: models list returned catalog data" || echo "FAIL: models list output was unexpected"
```

### QS-5. Skills list [CRITICAL]

```bash
uv run meridian --json skills list >/tmp/meridian-qs-skills.txt && \
grep -Eq 'skill-|slides|spreadsheets|meridian-' /tmp/meridian-qs-skills.txt && \
echo "PASS: skills list returned entries" || echo "FAIL: skills list output was unexpected"
```

### QS-6. Doctor [CRITICAL]

```bash
uv run meridian doctor >/tmp/meridian-qs-doctor.txt && \
grep -q '^ok:' /tmp/meridian-qs-doctor.txt && \
grep -q '^repo_root:' /tmp/meridian-qs-doctor.txt && \
echo "PASS: doctor returned health data" || echo "FAIL: doctor output was unexpected"
```

### QS-7. Spawn dry-run [CRITICAL]

```bash
uv run meridian --json spawn -p "quick sanity prompt" --dry-run > /tmp/meridian-qs-dryrun.json && \
python3 - <<'PY'
import json
doc = json.load(open("/tmp/meridian-qs-dryrun.json"))
assert doc["status"] == "dry-run"
assert "quick sanity prompt" in doc["composed_prompt"]
assert isinstance(doc["cli_command"], list) and doc["cli_command"]
print("PASS: spawn dry-run produced a composed prompt")
PY
```

### QS-8. Unknown command [IMPORTANT]

```bash
if uv run meridian nonexistent >/tmp/meridian-qs-unknown.out 2>&1; then
  echo "FAIL: unknown command unexpectedly succeeded"
elif grep -q "Unknown command" /tmp/meridian-qs-unknown.out; then
  echo "PASS: unknown command fails cleanly"
else
  echo "FAIL: unknown command error text was not useful"
fi
```

### QS-9. Spawn list [IMPORTANT]

```bash
uv run meridian --json spawn list >/tmp/meridian-qs-spawn-list.txt && \
(grep -Fxq '(no spawns)' /tmp/meridian-qs-spawn-list.txt || grep -Eq '^p[0-9]+' /tmp/meridian-qs-spawn-list.txt) && \
echo "PASS: spawn list returned a clean response" || echo "FAIL: spawn list output was unexpected"
```
