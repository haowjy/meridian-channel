# Managed Install Cycle

This is the full scratch-repo round trip for managed installs: install a source, verify repo-local state, update it, and remove it cleanly. Always override both `MERIDIAN_REPO_ROOT` and `MERIDIAN_STATE_ROOT` here.

## Setup

```bash
export REPO_ROOT=/abs/path/to/meridian-channel
rm -rf /tmp/meridian-sync-src /tmp/meridian-sync-empty /tmp/meridian-sync-repo
mkdir -p /tmp/meridian-sync-src/skills/demo /tmp/meridian-sync-src/agents /tmp/meridian-sync-empty /tmp/meridian-sync-repo
git -C /tmp/meridian-sync-repo init --quiet
for var in $(env | awk -F= '/^MERIDIAN_/ {print $1}'); do unset "$var"; done
export MERIDIAN_REPO_ROOT=/tmp/meridian-sync-repo
export MERIDIAN_STATE_ROOT=/tmp/meridian-sync-repo/.meridian
export UV_CACHE_DIR=/tmp/uv-cache
mkdir -p "$UV_CACHE_DIR"
cat > /tmp/meridian-sync-src/skills/demo/SKILL.md <<'EOF'
# Demo Skill

Body content.
EOF
cat > /tmp/meridian-sync-src/agents/helper.md <<'EOF'
# Helper Agent

Does things.
EOF
cd "$REPO_ROOT"
test "$MERIDIAN_STATE_ROOT" = "/tmp/meridian-sync-repo/.meridian" && echo "PASS: install setup isolated both env vars" || echo "FAIL: install setup leaked env vars"
```

### INSTALL-1. Install writes managed repo-local state [CRITICAL]

```bash
uv run meridian sources install /tmp/meridian-sync-src --name smoke-source >/tmp/meridian-sync-install.out 2>&1 && \
test -f /tmp/meridian-sync-repo/.agents/skills/demo/SKILL.md && \
test -f /tmp/meridian-sync-repo/.agents/agents/helper.md && \
test -f /tmp/meridian-sync-repo/.meridian/config.toml && \
test -f /tmp/meridian-sync-repo/.meridian/agents.lock && \
test ! -e /tmp/meridian-sync-repo/.claude/agents && \
test ! -e /tmp/meridian-sync-repo/.claude/skills && \
echo "PASS: install wrote expected managed files" || echo "FAIL: install did not write the expected managed files"
```

### INSTALL-2. Status reports the repo as healthy [IMPORTANT]

```bash
uv run meridian sources status >/tmp/meridian-sync-status.out 2>&1 && \
grep -Eiq 'in sync|ok|clean' /tmp/meridian-sync-status.out && \
echo "PASS: status reported a healthy managed state" || echo "FAIL: status output was unexpected"
```

### INSTALL-3. Update pulls source changes into managed files [IMPORTANT]

```bash
printf '\n## Updated upstream\n' >> /tmp/meridian-sync-src/agents/helper.md && \
uv run meridian sources update >/tmp/meridian-sync-update.out 2>&1 && \
grep -q 'Updated upstream' /tmp/meridian-sync-repo/.agents/agents/helper.md && \
echo "PASS: update refreshed managed content" || echo "FAIL: update missed source changes"
```

### INSTALL-4. Remove cleans up the managed source [IMPORTANT]

```bash
uv run meridian sources uninstall --source smoke-source >/tmp/meridian-sync-remove.out 2>&1 && \
test ! -e /tmp/meridian-sync-repo/.agents/skills/demo && \
test ! -e /tmp/meridian-sync-repo/.agents/agents/helper.md && \
echo "PASS: remove cleaned managed artifacts" || echo "FAIL: remove left managed artifacts behind"
```

### INSTALL-5. Invalid or empty sources fail cleanly [CRITICAL]

```bash
if uv run meridian sources install /tmp/meridian-sync-missing --name missing >/tmp/meridian-sync-invalid.out 2>&1; then
  echo "FAIL: missing source unexpectedly installed"
elif test ! -e /tmp/meridian-sync-repo/.meridian/agents.toml && \
     grep -qi 'does not exist' /tmp/meridian-sync-invalid.out; then
  echo "PASS: missing source failed without writing manifest state"
else
  echo "FAIL: missing source failure was not clean"
fi

if uv run meridian sources install /tmp/meridian-sync-empty --name empty >/tmp/meridian-sync-empty.out 2>&1; then
  echo "FAIL: empty source unexpectedly installed"
elif test ! -e /tmp/meridian-sync-repo/.meridian/agents.toml && \
     grep -qi 'No installable items found' /tmp/meridian-sync-empty.out; then
  echo "PASS: empty source failed without writing manifest state"
else
  echo "FAIL: empty source failure was not clean"
fi
```

### INSTALL-6. Rename updates remove the old managed path [IMPORTANT]

```bash
uv run meridian sources install /tmp/meridian-sync-src --name rename-source --agents helper --rename agent:helper=helper-one >/tmp/meridian-sync-rename-install.out 2>&1 && \
uv run python - <<'PY'
from pathlib import Path

manifest = Path("/tmp/meridian-sync-repo/.meridian/agents.toml")
text = manifest.read_text(encoding="utf-8")
text = text.replace('rename = { "agent:helper" = "helper-one" }', 'rename = { "agent:helper" = "helper-two" }')
manifest.write_text(text, encoding="utf-8")
PY
uv run meridian sources update >/tmp/meridian-sync-rename-update.out 2>&1 && \
test ! -e /tmp/meridian-sync-repo/.agents/agents/helper-one.md && \
test -f /tmp/meridian-sync-repo/.agents/agents/helper-two.md && \
echo "PASS: rename update pruned the old managed path" || echo "FAIL: rename update left stale managed files"
```

### INSTALL-7. Remote GitHub install works for a real repo [IMPORTANT]

Run this when you changed remote source resolution or lock semantics. This complements the local-path round trip above.

```bash
rm -rf /tmp/meridian-sync-gh-repo
mkdir -p /tmp/meridian-sync-gh-repo
git -C /tmp/meridian-sync-gh-repo init --quiet
export MERIDIAN_REPO_ROOT=/tmp/meridian-sync-gh-repo
export MERIDIAN_STATE_ROOT=/tmp/meridian-sync-gh-repo/.meridian
export UV_CACHE_DIR=/tmp/uv-cache
uv run meridian sources install haowjy/orchestrate --name orchestrate >/tmp/meridian-sync-gh-install.out 2>&1 && \
uv run meridian sources status >/tmp/meridian-sync-gh-status.out 2>&1 && \
grep -q '"locator": "https://github.com/haowjy/orchestrate.git"' /tmp/meridian-sync-gh-repo/.meridian/agents.lock && \
grep -q '"status": "in-sync"' /tmp/meridian-sync-gh-status.out && \
test ! -e /tmp/meridian-sync-gh-repo/.claude/skills/orchestrate && \
echo "PASS: remote GitHub install locked a real source without harness mirroring" || echo "FAIL: remote GitHub install did not behave as expected"
```
