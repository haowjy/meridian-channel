#!/usr/bin/env bash
# record-commit.sh — Record the latest commit and optionally update the handoff file.
#
# Usage:
#   scripts/record-commit.sh --plan <name> [--task <name>] [--update-handoff]
#
# Records the latest git commit into SESSION_DIR/plans/{plan}/commits/{NNN}-{hash}.md
# and optionally appends to handoffs/latest.md.

set -euo pipefail

# Resolve through symlinks (same pattern as run-agent.sh)
_source="${BASH_SOURCE[0]}"
while [[ -L "$_source" ]]; do
  _dir="$(cd "$(dirname "$_source")" && pwd -P)"
  _source="$(readlink "$_source")"
  [[ "$_source" != /* ]] && _source="$_dir/$_source"
done
SCRIPT_DIR="$(cd "$(dirname "$_source")" && pwd -P)"
CURRENT_DIR="$(pwd -P)"
REPO_ROOT="$(git -C "$CURRENT_DIR" rev-parse --show-toplevel 2>/dev/null || echo "$CURRENT_DIR")"
ORCHESTRATE_ROOT="${ORCHESTRATE_ROOT:-$REPO_ROOT/.orchestrate}"
SESSION_DIR="$ORCHESTRATE_ROOT/session"

# ─── Parse Args ──────────────────────────────────────────────────────────────

PLAN_NAME=""
SLICE_NAME=""
UPDATE_HANDOFF=false

usage() {
  cat <<'EOF'
Usage: scripts/record-commit.sh --plan <name> [--task <name>] [--update-handoff]

  --plan NAME          Plan name (required)
  --task NAME         Task name (optional)
  --update-handoff     Append commit info to handoffs/latest.md
  -h, --help           Show this help
EOF
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --plan)
      [[ $# -lt 2 ]] && { echo "ERROR: --plan requires a value." >&2; usage; }
      PLAN_NAME="$2"; shift 2 ;;
    --task)
      [[ $# -lt 2 ]] && { echo "ERROR: --task requires a value." >&2; usage; }
      SLICE_NAME="$2"; shift 2 ;;
    --update-handoff) UPDATE_HANDOFF=true; shift ;;
    -h|--help) usage ;;
    *) echo "ERROR: Unknown argument: $1" >&2; usage ;;
  esac
done

if [[ -z "$PLAN_NAME" ]]; then
  echo "ERROR: --plan is required." >&2
  usage
fi

# ─── Read Latest Commit ─────────────────────────────────────────────────────

COMMIT_HASH="$(git log -1 --format='%h')"
COMMIT_SUBJECT="$(git log -1 --format='%s')"
COMMIT_DATE="$(git log -1 --format='%ci')"
COMMIT_FULL_HASH="$(git log -1 --format='%H')"

# ─── Write Commit Record ────────────────────────────────────────────────────

COMMITS_DIR="$SESSION_DIR/plans/$PLAN_NAME/commits"
mkdir -p "$COMMITS_DIR"

# Determine next sequence number
LAST_NUM=$(ls "$COMMITS_DIR" 2>/dev/null | grep -oE '^[0-9]+' | sort -n | tail -1 || echo "0")
NEXT_NUM=$(printf "%03d" $((10#${LAST_NUM:-0} + 1)))

COMMIT_FILE="$COMMITS_DIR/${NEXT_NUM}-${COMMIT_HASH}.md"

cat > "$COMMIT_FILE" <<EOF
# Commit ${NEXT_NUM}: ${COMMIT_HASH}

- **Hash:** ${COMMIT_FULL_HASH}
- **Subject:** ${COMMIT_SUBJECT}
- **Date:** ${COMMIT_DATE}
- **Plan:** ${PLAN_NAME}
EOF

if [[ -n "$SLICE_NAME" ]]; then
  echo "- **Task:** ${SLICE_NAME}" >> "$COMMIT_FILE"
fi

echo "[record-commit] Recorded: $COMMIT_FILE" >&2

# ─── Update Handoff ─────────────────────────────────────────────────────────

if [[ "$UPDATE_HANDOFF" == true ]]; then
  HANDOFF_DIR="$SESSION_DIR/handoffs"
  mkdir -p "$HANDOFF_DIR"
  HANDOFF_FILE="$HANDOFF_DIR/latest.md"

  {
    echo ""
    echo "## Commit: ${COMMIT_HASH}"
    echo "- **Subject:** ${COMMIT_SUBJECT}"
    echo "- **Date:** ${COMMIT_DATE}"
    echo "- **Plan:** ${PLAN_NAME}"
    [[ -n "$SLICE_NAME" ]] && echo "- **Task:** ${SLICE_NAME}"
  } >> "$HANDOFF_FILE"

  echo "[record-commit] Updated handoff: $HANDOFF_FILE" >&2
fi
