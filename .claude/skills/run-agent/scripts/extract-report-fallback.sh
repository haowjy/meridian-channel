#!/usr/bin/env bash
# extract-report-fallback.sh — Extract last assistant message from harness output as report fallback.
#
# Usage: extract-report-fallback.sh <harness> <output.jsonl> <stderr.log> <exit-code>
# Writes report content to stdout.
# Exit 0 = report extracted, Exit 1 = fallback diagnostic produced.
#
# When an agent doesn't produce report.md, this script extracts the last assistant
# message from the harness output as a best-effort report.

set -euo pipefail

HARNESS="${1:?Usage: extract-report-fallback.sh <harness> <output.jsonl> <stderr.log> <exit-code>}"
OUTPUT="${2:?}"
STDERR_LOG="${3:?}"
EXIT_CODE="${4:?}"

_emit_diagnostic() {
  # Compact diagnostic when parsing fails — keep under 10 lines.
  echo "# Run Report (auto-generated)"
  echo ""
  echo "**Status**: $([ "$EXIT_CODE" -eq 0 ] && echo "completed" || echo "failed (exit $EXIT_CODE)")"

  if [[ -f "$OUTPUT" ]] && [[ -s "$OUTPUT" ]]; then
    local line_count
    line_count="$(wc -l < "$OUTPUT" 2>/dev/null || echo "0")"
    echo "**Output lines**: $line_count"
  fi

  if [[ -f "$STDERR_LOG" ]] && [[ -s "$STDERR_LOG" ]]; then
    echo ""
    echo "**Last error**:"
    echo '```'
    tail -3 "$STDERR_LOG" 2>/dev/null || true
    echo '```'
  fi
}

# Require jq
if ! command -v jq >/dev/null 2>&1; then
  _emit_diagnostic
  exit 1
fi

if [[ ! -f "$OUTPUT" ]] || [[ ! -s "$OUTPUT" ]]; then
  _emit_diagnostic
  exit 1
fi

last_message=""

case "$HARNESS" in
  claude)
    # Claude stream-json: look for assistant content blocks.
    # The last "result" event contains the final assistant message.
    last_message="$(grep '"type"' "$OUTPUT" 2>/dev/null \
      | jq -r '
        select(.type == "result")
        | .result.text // .result.content // empty
        | if type == "array" then
            [.[] | select(.type == "text") | .text] | join("\n")
          elif type == "string" then .
          else empty
          end
      ' 2>/dev/null \
      | tail -1 || echo "")"

    # Fallback: try content_block_delta events for streaming text
    if [[ -z "$last_message" ]]; then
      last_message="$(grep '"type"' "$OUTPUT" 2>/dev/null \
        | jq -r 'select(.type == "assistant") | .message.content // empty | if type == "array" then [.[] | select(.type == "text") | .text] | join("\n") elif type == "string" then . else empty end' 2>/dev/null \
        | tail -1 || echo "")"
    fi
    ;;

  codex)
    # Codex JSONL: look for item.completed events with assistant messages.
    last_message="$(grep '"type"' "$OUTPUT" 2>/dev/null \
      | jq -r '
        select(.type == "item.completed")
        | .item
        | select(.role == "assistant" or .type == "message")
        | .content // empty
        | if type == "array" then
            [.[] | select(.type == "text" or .type == "output_text") | (.text // .output_text // empty)] | join("\n")
          elif type == "string" then .
          else empty
          end
      ' 2>/dev/null \
      | tail -1 || echo "")"
    ;;

  opencode)
    # OpenCode JSON events: look for assistant responses.
    last_message="$(grep '"type"' "$OUTPUT" 2>/dev/null \
      | jq -r '
        select(.type == "assistant" or .type == "response")
        | .content // .text // .message // empty
        | if type == "array" then
            [.[] | select(.type == "text") | .text] | join("\n")
          elif type == "string" then .
          else empty
          end
      ' 2>/dev/null \
      | tail -1 || echo "")"
    ;;

  *)
    _emit_diagnostic
    exit 1
    ;;
esac

if [[ -n "$last_message" ]]; then
  echo "$last_message"
  exit 0
else
  _emit_diagnostic
  exit 1
fi
