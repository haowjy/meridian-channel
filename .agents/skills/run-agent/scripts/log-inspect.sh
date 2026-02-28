#!/usr/bin/env bash
# log-inspect.sh — jq-based conversation log inspector.
#
# Usage:
#   scripts/log-inspect.sh <mode> <output.json|output.jsonl> [pattern] [context]
#
# Modes:
#   summary  (default) — cost, tokens, turns, duration, models
#   tools    — tool call names + counts
#   errors   — is_error flags, permission denials
#   files    — delegates to extract-files-touched.sh

set -euo pipefail

# Resolve through symlinks
_source="${BASH_SOURCE[0]}"
while [[ -L "$_source" ]]; do
  _dir="$(cd "$(dirname "$_source")" && pwd -P)"
  _source="$(readlink "$_source")"
  [[ "$_source" != /* ]] && _source="$_dir/$_source"
done
SCRIPT_DIR="$(cd "$(dirname "$_source")" && pwd -P)"

# ─── Args ────────────────────────────────────────────────────────────────────

MODE="${1:-summary}"
LOG_FILE="${2:-}"
PATTERN="${3:-}"
CONTEXT="${4:-2}"

if [[ -z "$LOG_FILE" ]]; then
  cat <<'EOF'
Usage: scripts/log-inspect.sh <mode> <output.json|output.jsonl> [pattern] [context]

Modes:
  summary  (default)  Cost, tokens, turns, duration, models
  tools               Tool call names + counts from result text
  errors              is_error flags, permission denials
  files               Delegates to extract-files-touched.sh
  search              Find pattern and show surrounding context (args: pattern [context])
EOF
  exit 1
fi

if [[ ! -f "$LOG_FILE" ]]; then
  echo "ERROR: File not found: $LOG_FILE" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq is required but not installed." >&2
  echo "  Install: sudo apt-get install jq  (or brew install jq on macOS)" >&2
  exit 1
fi

# ─── Format Detection ───────────────────────────────────────────────────────
# Determine whether the file is a single JSON value or a JSONL stream.

detect_format() {
  if ! jq -e . "$LOG_FILE" >/dev/null 2>&1; then
    echo "text"
    return
  fi

  local item_count
  item_count="$(jq -s 'length' "$LOG_FILE" 2>/dev/null || echo 0)"
  if [[ "$item_count" == "1" ]]; then
    echo "json"
  else
    echo "jsonl"
  fi
}

detect_harness() {
  if [[ "$FORMAT" == "text" ]]; then
    echo "unknown"
    return
  fi

  # Codex JSONL commonly includes thread./turn. event types.
  if jq -sre 'any(.[]; (.type? // "" | tostring | test("^thread\\.|^turn\\.")))' "$LOG_FILE" >/dev/null 2>&1; then
    echo "codex"
    return
  fi

  # Claude stream-json commonly emits message/content_block event families.
  if jq -sre 'any(.[]; (.type? // "" | tostring | test("^message_|^content_block_")))' "$LOG_FILE" >/dev/null 2>&1; then
    echo "claude-stream-json"
    return
  fi

  # Claude single-json includes these top-level fields.
  if jq -e 'has("modelUsage") or has("permission_denials") or has("session_id")' "$LOG_FILE" >/dev/null 2>&1; then
    echo "claude"
    return
  fi

  # OpenCode JSON streams typically emit typed events but not codex thread./turn. prefixes.
  if jq -sre 'any(.[]; has("type"))' "$LOG_FILE" >/dev/null 2>&1; then
    echo "opencode-or-other-jsonl"
    return
  fi

  echo "unknown"
}

FORMAT="$(detect_format)"
HARNESS="$(detect_harness)"

# ─── Summary Mode ───────────────────────────────────────────────────────────

do_summary() {
  echo "═══ Log Summary ═══"
  echo "File: $LOG_FILE"
  echo "Format: $FORMAT"
  echo "Harness: $HARNESS"
  echo ""

  if [[ "$FORMAT" == "text" ]]; then
    local line_count
    line_count="$(wc -l < "$LOG_FILE")"
    echo "Lines: $line_count"
    echo "(Non-JSON log; structured summary unavailable)"
  elif [[ "$FORMAT" == "json" ]]; then
    # Claude single-JSON format
    # Claude output: cost is total_cost_usd, models are in modelUsage (object with model keys)
    jq -r '
      "Models:     " + (if .modelUsage then (.modelUsage | keys | join(", ")) elif .model then .model else "unknown" end),
      "Session ID: " + (.session_id // "unknown"),
      "Cost (USD): $" + ((.total_cost_usd // .cost_usd // 0) | tostring),
      "Duration:   " + (if .duration_ms then ((.duration_ms / 1000 * 100 | round / 100) | tostring) + "s" else "unknown" end),
      "Turns:      " + (if .num_turns then (.num_turns | tostring) else "unknown" end),
      "Result:     " + (.subtype // .stop_reason // "unknown"),
      "",
      "Tokens:",
      "  Input:  " + (if .usage.input_tokens then (.usage.input_tokens | tostring) else "unknown" end),
      "  Output: " + (if .usage.output_tokens then (.usage.output_tokens | tostring) else "unknown" end),
      "  Cache read:  " + (if .usage.cache_read_input_tokens then (.usage.cache_read_input_tokens | tostring) else "n/a" end),
      "  Cache write: " + (if .usage.cache_creation_input_tokens then (.usage.cache_creation_input_tokens | tostring) else "n/a" end)
    ' "$LOG_FILE" 2>/dev/null || echo "(Could not extract summary fields)"
  else
    # JSONL format — aggregate across events
    jq -sr '
      "Models:     " + (
        ([.[] | .model? // .model_name? // .response?.model? | strings] | unique) as $models |
        if ($models | length) > 0 then ($models | join(", ")) else "unknown" end
      ),
      "Session ID: " + (
        ([.[] | .session_id? // .thread_id? | strings] | unique | .[0]) // "unknown"
      ),
      "Events:     " + (length | tostring),
      "Errors:     " + (
        [.[] | select((.type? // "" | tostring | ascii_downcase | contains("error")) or (.is_error? == true) or (.error? != null))] | length | tostring
      ),
      "",
      "Event Types:",
      (
        [.[] | .type? | strings]
        | group_by(.)
        | map({k: .[0], v: length})
        | sort_by(-.v)
        | if length == 0 then ["  (none)"] else map("  \(.v)\t\(.k)") end
        | .[]
      )
    ' "$LOG_FILE" 2>/dev/null || echo "(Could not extract JSONL summary fields)"
  fi
}

# ─── Tools Mode ──────────────────────────────────────────────────────────────

do_tools() {
  echo "═══ Tool Calls ═══"

  if [[ "$FORMAT" == "text" ]]; then
    grep -oE '\b(Read|Write|Edit|Bash|Glob|Grep|WebSearch|WebFetch|Task|NotebookEdit|web_search|web_fetch|mcp__[A-Za-z0-9_.:-]+)\b' "$LOG_FILE" |
      sort | uniq -c | sort -rn | awk '{printf "%s\t%s\n", $1, $2}' ||
      echo "(No tool calls found)"
  else
    local tool_output
    tool_output="$(
      jq -sr '
        map(
          [
            (.. | objects
              | select((.type? // "" | tostring | ascii_downcase | test("tool|web_search|web_fetch|mcp")))
              | (.name? // .tool_name? // .tool? // .function?.name? // .toolName? // empty)
            ),
            (.. | objects | .tool_name? // empty),
            (.. | objects | .function?.name? // empty),
            (.. | objects
              | select((.name? != null) and ((.tool_call_id? != null) or (.call_id? != null) or (.type? // "" | tostring | ascii_downcase | contains("tool"))))
              | .name
            )
          ] | flatten | map(strings) | unique | .[]
        )
        | map(select(length > 0))
        | map(select(. != "unknown"))
        | group_by(.)
        | map({name: .[0], count: length})
        | sort_by(-.count)
        | .[]
        | "\(.count)\t\(.name)"
      ' "$LOG_FILE" 2>/dev/null || true
    )"

    if [[ -n "$tool_output" ]]; then
      echo "$tool_output"
    else
      # Text fallback across JSON payloads for common built-in and MCP-style tool names.
      jq -r '.. | strings' "$LOG_FILE" 2>/dev/null |
        grep -oE '\b(Read|Write|Edit|Bash|Glob|Grep|WebSearch|WebFetch|Task|NotebookEdit|web_search|web_fetch|mcp__[A-Za-z0-9_.:-]+)\b' |
        sort | uniq -c | sort -rn | awk '{printf "%s\t%s\n", $1, $2}' ||
        echo "(No tool calls found)"
    fi
  fi
}

# ─── Errors Mode ─────────────────────────────────────────────────────────────

do_errors() {
  echo "═══ Errors ═══"

  if [[ "$FORMAT" == "text" ]]; then
    local err_count
    err_count="$(grep -ciE 'error|failed|exception|denied' "$LOG_FILE" || true)"
    [[ -z "$err_count" ]] && err_count="0"
    echo "Error-pattern matches: $err_count"
    echo ""
    grep -iE 'error|failed|exception|denied' "$LOG_FILE" | head -20 || true
  elif [[ "$FORMAT" == "json" ]]; then
    # Check top-level is_error
    local is_error
    is_error="$(jq -r '.is_error // false' "$LOG_FILE" 2>/dev/null)"
    echo "Top-level is_error: $is_error"
    echo ""

    # Permission denials (structured field in Claude output)
    echo "Permission denials:"
    jq -r '
      if .permission_denials then
        (.permission_denials | tostring)
      else
        "  0"
      end
    ' "$LOG_FILE" 2>/dev/null || echo "  (could not extract)"

    # Check result for error patterns
    echo ""
    echo "Error patterns in result:"
    local err_count
    err_count="$(jq -r '.result // ""' "$LOG_FILE" 2>/dev/null | grep -ciE 'error|failed|exception' || true)"
    [[ -z "$err_count" ]] && err_count="0"
    echo "  Matches: $err_count"
  else
    local err_count
    err_count="$(jq -sr '[.[] | select((.type? // "" | tostring | ascii_downcase | contains("error")) or (.is_error? == true) or (.error? != null))] | length' "$LOG_FILE" 2>/dev/null || echo "0")"
    echo "Error events: $err_count"
    echo ""
    jq -sr '
      [.[] | select((.type? // "" | tostring | ascii_downcase | contains("error")) or (.is_error? == true) or (.error? != null))
       | (.message? // .error?.message? // .content? // (.error? | tostring) // "error event")]
      | .[:20]
      | if length == 0 then ["(none found)"] else . end
      | .[]
    ' "$LOG_FILE" 2>/dev/null || echo "(Could not parse JSONL errors)"
  fi
}

# ─── Files Mode ──────────────────────────────────────────────────────────────

do_files() {
  local extractor="$SCRIPT_DIR/extract-files-touched.sh"
  if [[ -x "$extractor" ]]; then
    "$extractor" "$LOG_FILE"
  else
    echo "ERROR: extract-files-touched.sh not found at $extractor" >&2
    exit 1
  fi
}

# ─── Search Mode ─────────────────────────────────────────────────────────────

do_search() {
  if [[ -z "$PATTERN" ]]; then
    echo "ERROR: search mode requires a pattern argument." >&2
    echo "Usage: scripts/log-inspect.sh search <output.json|output.jsonl> <pattern> [context]" >&2
    exit 1
  fi

  if ! [[ "$CONTEXT" =~ ^[0-9]+$ ]]; then
    echo "ERROR: context must be a non-negative integer (got: $CONTEXT)" >&2
    exit 1
  fi

  local target_file="$LOG_FILE"
  local tmp_file=""
  local max_lines=200

  # For single JSON, pretty-print first so context windows are readable.
  if [[ "$FORMAT" == "json" ]]; then
    tmp_file="$(mktemp)"
    if jq . "$LOG_FILE" > "$tmp_file" 2>/dev/null; then
      target_file="$tmp_file"
    else
      rm -f "$tmp_file"
      tmp_file=""
    fi
  fi

  echo "═══ Search Matches ═══"
  echo "File: $LOG_FILE"
  echo "Format: $FORMAT"
  echo "Pattern: $PATTERN"
  echo "Context: $CONTEXT"
  echo ""

  local matches
  matches="$(grep -n -i -C "$CONTEXT" -- "$PATTERN" "$target_file" 2>/dev/null || true)"
  if [[ -z "$matches" ]]; then
    echo "(No matches found)"
    [[ -n "$tmp_file" ]] && rm -f "$tmp_file"
    return 0
  fi

  # Prevent dumping very large logs into context.
  sed -n "1,${max_lines}p" <<< "$matches"
  local total_lines
  total_lines="$(echo "$matches" | wc -l | tr -d ' ')"
  if [[ "$total_lines" -gt "$max_lines" ]]; then
    echo ""
    echo "(truncated: showing first $max_lines of $total_lines lines)"
  fi

  [[ -n "$tmp_file" ]] && rm -f "$tmp_file"
  return 0
}

# ─── Dispatch ────────────────────────────────────────────────────────────────

case "$MODE" in
  summary) do_summary ;;
  tools)   do_tools ;;
  errors)  do_errors ;;
  files)   do_files ;;
  search)  do_search ;;
  *)
    echo "ERROR: Unknown mode: $MODE" >&2
    echo "Valid modes: summary, tools, errors, files, search" >&2
    exit 1
    ;;
esac
