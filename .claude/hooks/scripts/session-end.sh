#!/usr/bin/env bash
# session-end.sh — SessionEnd hook (packaged with orchestrate plugin)
#
# On clear, saves the outgoing transcript path so session-start.sh can
# check if ExitPlanMode was the last action (plan acceptance vs manual /clear).
#
# Input: JSON on stdin with { session_id, transcript_path, reason, cwd, ... }
# Output: JSON on stdout (empty — no additionalContext needed)

set -euo pipefail

# --- Source shared helpers ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

# ============================================================================
# Parse hook input
# ============================================================================
INPUT=$(cat)
REASON=$(echo "$INPUT" | jq -r '.reason // empty')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty')

# Only act on clear
if [[ "$REASON" != "clear" ]]; then
  echo '{}'
  exit 0
fi

# Need a transcript to save
if [[ -z "$TRANSCRIPT_PATH" || ! -f "$TRANSCRIPT_PATH" ]]; then
  echo '{}'
  exit 0
fi

# Resolve project root from CWD
PROJECT_ROOT="$(find_project_root "${CWD:-$PWD}")" || { echo '{}'; exit 0; }

# Save the outgoing transcript path for session-start.sh to pick up
BREADCRUMB="$PROJECT_ROOT/.orchestrate/session/prev-transcript"
mkdir -p "$(dirname "$BREADCRUMB")"
echo "$TRANSCRIPT_PATH" > "$BREADCRUMB"

echo '{}'
