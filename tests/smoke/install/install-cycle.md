# Managed Install Cycle

This is the full scratch-repo round trip for managed installs: install a source, verify repo-local state, update it, and remove it cleanly. Always override both `MERIDIAN_REPO_ROOT` and `MERIDIAN_STATE_ROOT` here.

## Setup

```bash
export REPO_ROOT=/abs/path/to/meridian-channel
rm -rf /tmp/meridian-sync-src /tmp/meridian-sync-repo
mkdir -p /tmp/meridian-sync-src/skills/demo /tmp/meridian-sync-src/agents /tmp/meridian-sync-repo
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
uv run meridian install /tmp/meridian-sync-src --name smoke-source >/tmp/meridian-sync-install.out 2>&1 && \
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
uv run meridian status >/tmp/meridian-sync-status.out 2>&1 && \
grep -Eiq 'in sync|ok|clean' /tmp/meridian-sync-status.out && \
echo "PASS: status reported a healthy managed state" || echo "FAIL: status output was unexpected"
```

### INSTALL-3. Update pulls source changes into managed files [IMPORTANT]

```bash
printf '\n## Updated upstream\n' >> /tmp/meridian-sync-src/agents/helper.md && \
uv run meridian update >/tmp/meridian-sync-update.out 2>&1 && \
grep -q 'Updated upstream' /tmp/meridian-sync-repo/.agents/agents/helper.md && \
echo "PASS: update refreshed managed content" || echo "FAIL: update missed source changes"
```

### INSTALL-4. Remove cleans up the managed source [IMPORTANT]

```bash
uv run meridian remove smoke-source >/tmp/meridian-sync-remove.out 2>&1 && \
test ! -e /tmp/meridian-sync-repo/.agents/skills/demo && \
test ! -e /tmp/meridian-sync-repo/.agents/agents/helper.md && \
echo "PASS: remove cleaned managed artifacts" || echo "FAIL: remove left managed artifacts behind"
```

### INSTALL-5. Remote GitHub install works for a real repo [IMPORTANT]

Run this when you changed remote source resolution or lock semantics. This complements the local-path round trip above.

```bash
rm -rf /tmp/meridian-sync-gh-repo
mkdir -p /tmp/meridian-sync-gh-repo
git -C /tmp/meridian-sync-gh-repo init --quiet
export MERIDIAN_REPO_ROOT=/tmp/meridian-sync-gh-repo
export MERIDIAN_STATE_ROOT=/tmp/meridian-sync-gh-repo/.meridian
export UV_CACHE_DIR=/tmp/uv-cache
uv run meridian install haowjy/orchestrate --name orchestrate >/tmp/meridian-sync-gh-install.out 2>&1 && \
uv run meridian status >/tmp/meridian-sync-gh-status.out 2>&1 && \
grep -q '"locator": "https://github.com/haowjy/orchestrate.git"' /tmp/meridian-sync-gh-repo/.meridian/agents.lock && \
grep -q '"status": "in-sync"' /tmp/meridian-sync-gh-status.out && \
test ! -e /tmp/meridian-sync-gh-repo/.claude/skills/orchestrate && \
echo "PASS: remote GitHub install locked a real source without harness mirroring" || echo "FAIL: remote GitHub install did not behave as expected"
```
