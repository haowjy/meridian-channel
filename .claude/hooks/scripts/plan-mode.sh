#!/usr/bin/env bash
# plan-mode.sh — PreToolUse hook for EnterPlanMode (packaged with orchestrate plugin)
#
# When Claude enters plan mode, inject a reminder to load the mermaid skill.
# Design docs and plans must use Mermaid diagrams per project conventions.
#
# Input: JSON on stdin with tool_name, tool_input, etc.
# Output: JSON with additionalContext on stdout

set -euo pipefail

# --- Source shared helpers (for consistency; not currently needed) ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

jq -n '{
  "additionalContext": "You are entering plan mode. Load the `mermaid` skill now (use the Skill tool with skill: \"mermaid\") — design docs and plans MUST use Mermaid diagrams for data flows, architecture, and state transitions."
}'
