# State Integrity

Run these checks after any smoke test that creates `.meridian/` state. The goal is to catch malformed JSONL, missing guard files, or stale lock behavior before it becomes a debugging session.

## Setup

```bash
export REPO_ROOT=/abs/path/to/meridian-channel
export SMOKE_REPO="$(mktemp -d /tmp/meridian-state.XXXXXX)"
git -C "$SMOKE_REPO" init --quiet
for var in $(env | awk -F= '/^MERIDIAN_/ {print $1}'); do unset "$var"; done
export MERIDIAN_REPO_ROOT="$SMOKE_REPO"
export MERIDIAN_STATE_ROOT="$SMOKE_REPO/.meridian"
cd "$REPO_ROOT"
uv run meridian --help >/dev/null && echo "PASS: base state fixture created" || echo "FAIL: state fixture setup failed"
```

### STATE-1. Core `.meridian/` structure exists [CRITICAL]

```bash
test -d "$MERIDIAN_STATE_ROOT/fs" && \
test -d "$MERIDIAN_STATE_ROOT/spawns" && \
test -f "$MERIDIAN_STATE_ROOT/.gitignore" && \
echo "PASS: core state directories exist" || echo "FAIL: core state directories are incomplete"
```

### STATE-2. `spawns.jsonl` contains valid JSON objects [IMPORTANT]

```bash
uv run python - <<'PY'
import json, os, sys
path = os.path.join(os.environ["MERIDIAN_STATE_ROOT"], "spawns.jsonl")
if not os.path.exists(path):
    print("PASS: no spawns.jsonl yet; run lifecycle smoke to populate it")
else:
    with open(path) as fh:
        lines = [line.strip() for line in fh if line.strip()]
    assert lines
    for line in lines:
        doc = json.loads(line)
        assert isinstance(doc, dict)
        assert "spawn_id" in doc or "id" in doc
    print("PASS: spawns.jsonl is well-formed")
PY
```

### STATE-3. `sessions.jsonl` is valid when present [IMPORTANT]

```bash
uv run python - <<'PY'
import json, os
path = os.path.join(os.environ["MERIDIAN_STATE_ROOT"], "sessions.jsonl")
if not os.path.exists(path):
    print("PASS: sessions.jsonl has not been created yet")
else:
    with open(path) as fh:
        for line in fh:
            if line.strip():
                assert isinstance(json.loads(line), dict)
    print("PASS: sessions.jsonl is well-formed")
PY
```

### STATE-4. Lock files are not left unusable [IMPORTANT]

```bash
uv run python - <<'PY'
import fcntl, glob, os
root = os.environ["MERIDIAN_STATE_ROOT"]
locks = glob.glob(os.path.join(root, "*.lock"))
if not locks:
    print("PASS: no lock files are present")
else:
    for path in locks:
        with open(path, "a+b") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    print("PASS: lock files are acquirable")
PY
```

### STATE-5. No stale flock sidecars remain after setup [NICE-TO-HAVE]

```bash
if find "$MERIDIAN_STATE_ROOT" -name '*.flock' -print | grep -q .; then
  echo "FAIL: stale .flock files remain"
else
  echo "PASS: no stale .flock sidecars remain"
fi
```
