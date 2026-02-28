#!/usr/bin/env bash
# extract-harness-session-id.sh — Extract harness-native session/thread ID from run output.
#
# Usage: extract-harness-session-id.sh <harness> <output.jsonl>
# Prints the harness session ID to stdout, exits non-zero if not found.
#
# Harness-specific extraction:
#   claude:   session_id from type=result event (skip hook events)
#   codex:    thread_id from first line (thread.started event only)
#   opencode: sessionID from first event

set -euo pipefail

HARNESS="${1:?Usage: extract-harness-session-id.sh <harness> <output.jsonl>}"
OUTPUT="${2:?Usage: extract-harness-session-id.sh <harness> <output.jsonl>}"

if [[ ! -f "$OUTPUT" ]] || [[ ! -s "$OUTPUT" ]]; then
  exit 1
fi

# Require jq for JSON parsing
if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq is required for session ID extraction" >&2
  exit 1
fi

session_id=""

case "$HARNESS" in
  claude)
    # Extract from first "result" event — avoids hook events which carry different session IDs.
    # Claude stream-json: each line is a JSON object with "type" field.
    session_id="$(grep '"type"' "$OUTPUT" 2>/dev/null \
      | jq -r 'select(.type == "result") | .session_id // empty' 2>/dev/null \
      | head -1 || echo "")"

    # Fallback: try system/init event
    if [[ -z "$session_id" ]]; then
      session_id="$(grep '"type"' "$OUTPUT" 2>/dev/null \
        | jq -r 'select(.type == "system" and .subtype != "hook_started" and .subtype != "hook_response") | .session_id // empty' 2>/dev/null \
        | head -1 || echo "")"
    fi
    ;;

  codex)
    # thread_id only appears on the first event (thread.started).
    session_id="$(head -1 "$OUTPUT" | jq -r '.thread_id // empty' 2>/dev/null || echo "")"
    ;;

  opencode)
    # sessionID is on every event; take from first line.
    session_id="$(head -1 "$OUTPUT" | jq -r '.sessionID // empty' 2>/dev/null || echo "")"
    ;;

  *)
    echo "ERROR: Unknown harness: $HARNESS" >&2
    exit 1
    ;;
esac

if [[ -z "$session_id" ]]; then
  exit 1
fi

echo "$session_id"
