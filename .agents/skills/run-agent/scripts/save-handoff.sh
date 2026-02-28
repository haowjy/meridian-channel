#!/usr/bin/env bash
# Save a timestamped handoff snapshot.
# Called by the orchestrator (or a Claude Code hook) before context compaction.
#
# Usage: scripts/save-handoff.sh <plan-dir>
#   plan-dir: path to the plan session directory (e.g., $SESSION_DIR/plans/my-plan)

set -euo pipefail

PLAN_DIR="${1:?Usage: scripts/save-handoff.sh <plan-dir>}"

if [[ ! -d "$PLAN_DIR/handoffs" ]]; then
  echo "ERROR: No handoffs directory at $PLAN_DIR/handoffs" >&2
  exit 1
fi

LATEST="$PLAN_DIR/handoffs/latest.md"
if [[ ! -f "$LATEST" ]]; then
  echo "No latest.md to snapshot — skipping." >&2
  exit 0
fi

TIMESTAMP=$(date -u +"%Y-%m-%dT%H-%M")
DEST="$PLAN_DIR/handoffs/${TIMESTAMP}.md"

cp "$LATEST" "$DEST"
echo "Handoff saved: $DEST"
